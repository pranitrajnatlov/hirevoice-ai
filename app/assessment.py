"""
Structured assessment generator — Phase 3.

Produces a schema-validated AssessmentResult from a completed interview transcript.
Handles JSON fences, field coercion, and retry logic for small models.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from app import llm
from app.config import PROMPTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class AssessmentResult:
    candidate_name: Optional[str] = None
    role_assessed: str = "Software Engineer"
    overall_score: int = 0
    technical_score: int = 0
    communication_score: int = 0
    culture_fit_score: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    technical_highlights: list[str] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    recommendation: str = "pending"
    summary: str = ""
    suggested_next_steps: list[str] = field(default_factory=list)
    parse_error: bool = False
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_valid(self) -> bool:
        return (
            not self.parse_error
            and 1 <= self.overall_score <= 10
            and self.recommendation in ("strong_hire", "hire", "maybe", "no_hire", "pending")
        )

    def to_display(self) -> str:
        if self.parse_error:
            return f"Assessment (raw output):\n{self.raw_output}"

        rec_map = {
            "strong_hire": "STRONG HIRE",
            "hire": "HIRE",
            "maybe": "MAYBE",
            "no_hire": "NO HIRE",
            "pending": "PENDING",
        }
        rec_label = rec_map.get(self.recommendation, self.recommendation.upper())

        lines = [
            "=== Interview Assessment ===",
            "",
            f"Recommendation: {rec_label}   Overall: {self.overall_score}/10",
            f"Technical: {self.technical_score}/10   Communication: {self.communication_score}/10   Culture Fit: {self.culture_fit_score}/10",
            "",
        ]
        if self.summary:
            lines += ["Summary:", self.summary, ""]
        if self.strengths:
            lines.append("Strengths:")
            lines += [f"  + {s}" for s in self.strengths]
            lines.append("")
        if self.weaknesses:
            lines.append("Areas for development:")
            lines += [f"  - {w}" for w in self.weaknesses]
            lines.append("")
        if self.red_flags:
            lines.append("Red flags:")
            lines += [f"  ! {r}" for r in self.red_flags]
            lines.append("")
        if self.suggested_next_steps:
            lines.append("Suggested next steps:")
            lines += [f"  > {s}" for s in self.suggested_next_steps]
        return "\n".join(lines)


def _load_system_prompt() -> str:
    path = PROMPTS_DIR / "assessment_system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "You are an expert hiring assessor. "
        "Given an interview transcript, output ONLY a JSON object."
    )


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> str:
    """Find first {...} block in text."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return text


def _coerce_score(value: Any, default: int = 5) -> int:
    """Clamp a score value to 1-10."""
    try:
        v = int(value)
        return max(1, min(10, v))
    except (TypeError, ValueError):
        return default


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x]
    if isinstance(value, str) and value:
        return [value]
    return []


def _coerce_recommendation(value: Any) -> str:
    valid = {"strong_hire", "hire", "maybe", "no_hire"}
    s = str(value).lower().replace(" ", "_")
    return s if s in valid else "maybe"


def _parse_assessment(raw: str) -> AssessmentResult:
    """Parse and coerce LLM output into an AssessmentResult."""
    cleaned = _strip_fences(raw)
    json_str = _extract_json(cleaned)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed: %s — raw: %s", exc, raw[:200])
        return AssessmentResult(parse_error=True, raw_output=raw)

    # Coerce each field defensively
    return AssessmentResult(
        candidate_name=data.get("candidate_name") or None,
        role_assessed=str(data.get("role_assessed") or "Software Engineer"),
        overall_score=_coerce_score(data.get("overall_score"), 5),
        technical_score=_coerce_score(data.get("technical_score"), 5),
        communication_score=_coerce_score(data.get("communication_score"), 5),
        culture_fit_score=_coerce_score(data.get("culture_fit_score"), 5),
        strengths=_coerce_list(data.get("strengths")),
        weaknesses=_coerce_list(data.get("weaknesses")),
        technical_highlights=_coerce_list(data.get("technical_highlights")),
        red_flags=_coerce_list(data.get("red_flags")),
        recommendation=_coerce_recommendation(data.get("recommendation")),
        summary=str(data.get("summary") or ""),
        suggested_next_steps=_coerce_list(data.get("suggested_next_steps")),
        raw_output=raw,
    )


def generate_assessment(
    transcript: str,
    resume_context: str = "",
    max_retries: int = 2,
) -> AssessmentResult:
    """
    Generate a validated assessment from an interview transcript.

    Retries up to max_retries times if the output fails to parse.
    Always returns an AssessmentResult (never raises).
    """
    system = _load_system_prompt()
    user_content = _build_user_message(transcript, resume_context)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    last_raw = ""
    for attempt in range(max_retries + 1):
        try:
            raw = llm.chat(messages, temperature=0.1, max_tokens=800)
            last_raw = raw
            result = _parse_assessment(raw)
            if result.is_valid():
                logger.info("Assessment generated (attempt %d): score=%s rec=%s",
                            attempt + 1, result.overall_score, result.recommendation)
                return result
            if attempt < max_retries:
                logger.warning("Assessment attempt %d invalid (score=%s) — retrying",
                               attempt + 1, result.overall_score)
                # Add a repair hint on retry
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "The JSON was not valid. Fix it: ensure overall_score is an integer 1-10, "
                        "recommendation is one of: strong_hire, hire, maybe, no_hire. "
                        "Return ONLY the corrected JSON object."
                    ),
                })
        except Exception as exc:
            logger.error("Assessment LLM call failed (attempt %d): %s", attempt + 1, exc)
            last_raw = str(exc)

    logger.warning("Assessment failed after %d attempts — returning raw output", max_retries + 1)
    return AssessmentResult(parse_error=True, raw_output=last_raw)


def _build_user_message(transcript: str, resume_context: str) -> str:
    parts = []
    if resume_context:
        parts.append(f"## Candidate Resume\n{resume_context.strip()}")
    parts.append(f"## Interview Transcript\n{transcript.strip()}")
    parts.append("Generate the assessment JSON now.")
    return "\n\n".join(parts)
