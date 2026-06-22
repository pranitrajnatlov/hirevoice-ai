"""
Interview context engineering (spec #6, #12) — deterministic, no model dependency.

- ``build_interview_context``: render a structured resume profile into a compact,
  model-friendly block (replaces dumping raw resume text into prompts).
- ``assess_answer_quality``: heuristically judge whether an answer is weak so the
  interview engine can decide to probe deeper (follow-up) vs. advance to a new topic.
- ``uncovered_skills``: pick the next resume skill not yet discussed (targets gaps).
"""

from __future__ import annotations

import re

_HEDGE_MARKERS = (
    "not sure", "i think", "i guess", "maybe", "kind of", "sort of", "i don't know",
    "i dont know", "probably", "i'm not certain", "no idea", "hard to say",
)
_FILLER = re.compile(r"\b(um+|uh+|like|you know|basically|actually|literally)\b", re.I)
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]*")


def _val(field):
    return field.get("value") if isinstance(field, dict) else field


def build_interview_context(profile: dict) -> str:
    """Render the structured profile into the compact context block from spec #6."""
    if not profile:
        return ""
    lines: list[str] = ["Candidate"]

    pi = profile.get("personal_information") or {}
    name = _val(pi.get("name"))
    if name:
        lines.append(f"Name: {name}")

    exp = profile.get("experience") or []
    if exp:
        lines.append("\nExperience:")
        for e in exp[:5]:
            title = _val(e.get("title")) or "Role"
            company = _val(e.get("company"))
            dates = _val(e.get("dates"))
            head = f"* {title}" + (f" at {company}" if company else "") + (f" ({dates})" if dates else "")
            lines.append(head)
            techs = [_val(t) or t for t in (e.get("technologies") or [])]
            if techs:
                lines.append(f"  Tech: {', '.join(techs[:8])}")

    skills = [_val(s) for s in (profile.get("skills") or [])]
    skills = [s for s in skills if s]
    if skills:
        lines.append("\nSkills:")
        lines.extend(f"* {s}" for s in skills[:20])

    projects = profile.get("projects") or []
    if projects:
        lines.append("\nProjects:")
        for p in projects[:5]:
            pname = _val(p.get("name"))
            if pname:
                techs = [_val(t) or t for t in (p.get("technologies") or [])]
                suffix = f" — {', '.join(techs[:5])}" if techs else ""
                lines.append(f"* {pname}{suffix}")

    edu = profile.get("education") or []
    if edu:
        degrees = [(_val(e.get("degree")) or _val(e.get("institution")) or e.get("raw")) for e in edu]
        degrees = [d for d in degrees if d]
        if degrees:
            lines.append("\nEducation:")
            lines.extend(f"* {d}" for d in degrees[:4])

    return "\n".join(lines).strip()


def resume_skills(profile: dict) -> list[str]:
    """Flat list of canonical skills (+ project/experience technologies) for coverage tracking."""
    out: list[str] = []
    for s in profile.get("skills") or []:
        v = _val(s)
        if v:
            out.append(v)
    for group in ("experience", "projects"):
        for item in profile.get(group) or []:
            out.extend(_val(t) or t for t in (item.get("technologies") or []))
    # de-dupe, preserve order
    seen, uniq = set(), []
    for s in out:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq


def uncovered_skills(profile: dict, covered: list[str]) -> list[str]:
    """Resume skills not yet discussed (case-insensitive), for targeting the next question."""
    cov = {c.lower() for c in covered}
    return [s for s in resume_skills(profile) if s.lower() not in cov]


def assess_answer_quality(question: str, answer: str) -> dict:
    """
    Heuristically classify an answer as weak/strong (spec #12) — no model needed.

    Weak when: very short, dominated by hedging/filler, or low lexical overlap with the
    technical terms in the question. Returns {weak, reasons, word_count, overlap}.
    """
    answer = (answer or "").strip()
    words = _WORD_RE.findall(answer.lower())
    wc = len(words)
    reasons: list[str] = []

    if wc < 12:
        reasons.append("very_short")

    low = answer.lower()
    hedges = sum(low.count(h) for h in _HEDGE_MARKERS)
    if hedges and wc < 40:
        reasons.append("hedging")

    fillers = len(_FILLER.findall(answer))
    if wc and fillers / max(wc, 1) > 0.25:
        reasons.append("filler_heavy")

    # Lexical overlap with the question's content words (does the answer engage the topic?).
    q_words = {w for w in _WORD_RE.findall(question.lower()) if len(w) > 3}
    a_words = set(words)
    overlap = len(q_words & a_words) / len(q_words) if q_words else 1.0
    if q_words and overlap < 0.08 and wc < 30:
        reasons.append("off_topic")

    return {
        "weak": bool(reasons),
        "reasons": reasons,
        "word_count": wc,
        "overlap": round(overlap, 2),
    }


# ── Adaptive strategy (spec #4) ────────────────────────────────────────────────
def infer_experience_level(profile: dict) -> str:
    """
    Classify the candidate as junior / mid / senior (spec #4), deterministically.

    Prefers ``years_experience`` (from LLM resume enrichment), falling back to the
    number of experience entries when years aren't available.
    """
    if not profile:
        return "mid"
    yrs = profile.get("years_experience")
    if isinstance(yrs, str):
        m = re.search(r"\d+(?:\.\d+)?", yrs)
        yrs = float(m.group(0)) if m else None
    if isinstance(yrs, (int, float)):
        if yrs < 2:
            return "junior"
        if yrs < 6:
            return "mid"
        return "senior"
    n = len(profile.get("experience") or [])
    if n <= 1:
        return "junior"
    if n <= 2:
        return "mid"
    return "senior"


# ── Conversation memory (spec #8) ──────────────────────────────────────────────
def empty_memory() -> dict:
    return {
        "covered_topics": [],
        "validated_skills": [],
        "weak_areas": [],
        "strong_areas": [],
        "confidence_samples": [],
    }


def update_memory(memory: dict, *, question: str, answer: str, quality: dict,
                  skills_in_answer: list[str]) -> dict:
    """Fold one Q/A turn into the running interview memory (spec #8). Pure; returns a new dict."""
    m = {**empty_memory(), **(memory or {})}
    topic = (question or "").strip()[:80]
    if topic and topic not in m["covered_topics"]:
        m["covered_topics"] = m["covered_topics"][-15:] + [topic]

    weak = bool(quality.get("weak"))
    for sk in skills_in_answer:
        bucket = "weak_areas" if weak else "validated_skills"
        if sk not in m[bucket]:
            m[bucket] = m[bucket] + [sk]
        # a validated skill shouldn't linger in weak (and vice-versa)
        other = "validated_skills" if weak else "weak_areas"
        m[other] = [s for s in m[other] if s != sk]

    summary = (answer or "").strip()[:70]
    if summary and not weak and summary not in m["strong_areas"]:
        m["strong_areas"] = (m["strong_areas"] + [summary])[-8:]

    m["confidence_samples"] = (m["confidence_samples"] + [0.0 if weak else 1.0])[-20:]
    return m


def memory_confidence(memory: dict) -> float:
    samples = (memory or {}).get("confidence_samples") or []
    return round(sum(samples) / len(samples), 2) if samples else 0.5


def build_memory_summary(memory: dict) -> str:
    """Compact, model-friendly recap so the AI avoids duplicate questions (spec #8)."""
    if not memory:
        return ""
    lines: list[str] = []
    if memory.get("covered_topics"):
        lines.append("Already asked about: " + "; ".join(memory["covered_topics"][-8:]))
    if memory.get("validated_skills"):
        lines.append("Skills the candidate demonstrated well: " + ", ".join(memory["validated_skills"][:12]))
    if memory.get("weak_areas"):
        lines.append("Shaky / unclear areas worth revisiting: " + ", ".join(memory["weak_areas"][:8]))
    return "\n".join(lines)
