"""
Interview orchestrator — manages conversation state and voice loop.

Phase 2: structured stage machine (Opening → Technical → Behavioral → Closing),
resume file upload support, post-interview assessment.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from app import llm, stt, tts
from app.config import MAX_INTERVIEW_TURNS, PROMPTS_DIR, ensure_dirs
from utils.resource_manager import get_resource_manager

logger = logging.getLogger(__name__)


class InterviewState(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    ENDED = "ended"


class InterviewStage(str, Enum):
    OPENING = "opening"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    CLOSING = "closing"


# How many candidate turns each stage gets
_STAGE_TURNS = {
    InterviewStage.OPENING: 1,
    InterviewStage.TECHNICAL: 4,
    InterviewStage.BEHAVIORAL: 2,
    InterviewStage.CLOSING: 1,
}

_STAGE_ORDER = [
    InterviewStage.OPENING,
    InterviewStage.TECHNICAL,
    InterviewStage.BEHAVIORAL,
    InterviewStage.CLOSING,
]

_STAGE_INSTRUCTIONS = {
    InterviewStage.OPENING: (
        "This is the opening. Greet the candidate warmly by name if available. "
        "Ask one icebreaker question about their background or current role."
    ),
    InterviewStage.TECHNICAL: (
        "This is the technical deep-dive. Ask a specific technical question about "
        "their experience, tools, or a project from their resume. "
        "Probe depth: ask follow-ups about trade-offs, failures, and design decisions."
    ),
    InterviewStage.BEHAVIORAL: (
        "This is the behavioral stage. Ask a STAR-format question about teamwork, "
        "handling conflict, taking ownership, or a time they learned from a mistake."
    ),
    InterviewStage.CLOSING: (
        "This is the closing stage. Thank the candidate for their time. "
        "Ask if they have any questions for you. "
        "Then wrap up with: 'That wraps up my questions for today. "
        "Thank you for your time — we will be in touch soon.'"
    ),
}


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class InterviewSession:
    state: InterviewState = InterviewState.IDLE
    stage: InterviewStage = InterviewStage.OPENING
    turns: list[Turn] = field(default_factory=list)
    resume_context: str = ""
    turn_count: int = 0
    stage_turn_count: int = 0
    greeting_sent: bool = False

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append(Turn(role=role, content=content))
        if role == "user":
            self.turn_count += 1
            self.stage_turn_count += 1

    def to_messages(self) -> list[dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def advance_stage(self) -> bool:
        """Move to next stage if current stage quota is met. Returns True if advanced."""
        budget = _STAGE_TURNS.get(self.stage, 1)
        if self.stage_turn_count >= budget:
            idx = _STAGE_ORDER.index(self.stage)
            if idx + 1 < len(_STAGE_ORDER):
                self.stage = _STAGE_ORDER[idx + 1]
                self.stage_turn_count = 0
                logger.info("Advanced to stage: %s", self.stage.value)
                return True
        return False

    def is_complete(self) -> bool:
        if self.turn_count >= MAX_INTERVIEW_TURNS:
            return True
        if self.stage == InterviewStage.CLOSING and self.stage_turn_count >= 1:
            return True
        if self.turns:
            last = self.turns[-1].content.lower()
            end_phrases = (
                "wraps up my questions",
                "thank you for your time",
                "we will be in touch",
                "we'll be in touch",
                "end interview",
                "that's all",
            )
            if any(p in last for p in end_phrases):
                return True
        return False


def _load_system_prompt() -> str:
    path = PROMPTS_DIR / "interviewer_system.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "CRITICAL: This is a VOICE interview. Never use asterisks, bold, bullets, or markdown. "
        "You are a professional technical interviewer. "
        "Ask one clear question at a time. Keep responses to 2-4 spoken sentences."
    )


class Interviewer:
    """Manages a single interview session with resource-aware model usage."""

    def __init__(self) -> None:
        self.session = InterviewSession()
        self.session_id: str = ""
        self._system_prompt = _load_system_prompt()
        self._rm = get_resource_manager()
        ensure_dirs()

    def start(self, resume_context: str = "") -> tuple[str, str]:
        """
        Begin interview. Returns (greeting_text, greeting_audio_path).
        Models load lazily on first use.
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"{ts}_{uuid.uuid4().hex[:6]}"
        self.session = InterviewSession(
            state=InterviewState.ACTIVE,
            resume_context=resume_context,
        )
        self._rm.set_interview_active(True)

        messages = [
            {"role": "system", "content": self._build_system_message()},
            {"role": "user", "content": "Begin the interview now."},
        ]

        greeting = llm.chat(messages, temperature=0.7, max_tokens=256)
        self.session.add_turn("assistant", greeting)
        self.session.greeting_sent = True

        audio_path = tts.synthesize(greeting)

        # Pre-load STT now so the candidate's first answer is transcribed instantly
        # instead of paying model load/download latency mid-interview.
        try:
            stt.warm()
        except Exception as exc:
            logger.warning("STT pre-warm failed (will load on first answer): %s", exc)

        logger.info("Interview started — stage=%s greeting: %s", self.session.stage.value, greeting[:80])
        return greeting, audio_path

    def process_candidate_audio(self, audio) -> tuple[str, str, str]:
        """
        Process one candidate audio turn.

        Returns:
            (transcript, ai_response_text, ai_response_audio_path)
        """
        if self.session.state != InterviewState.ACTIVE:
            raise RuntimeError("Interview is not active")

        transcript = stt.transcribe(audio)
        if not transcript.strip():
            no_audio_reply = "I did not catch that. Could you please repeat your answer?"
            audio_path = tts.synthesize(no_audio_reply)
            return "", no_audio_reply, audio_path

        self.session.add_turn("user", transcript)
        self.session.advance_stage()

        messages = [{"role": "system", "content": self._build_system_message()}]
        messages.extend(self.session.to_messages())

        response = llm.chat(messages, temperature=0.7, max_tokens=300)
        self.session.add_turn("assistant", response)

        audio_path = tts.synthesize(response)

        if self.session.is_complete():
            self.end()

        return transcript, response, audio_path

    def end(self) -> str:
        """End interview and trigger resource cleanup."""
        self.session.state = InterviewState.ENDED
        summary = self._rm.set_interview_active(False) or self._rm.cleanup_all()
        logger.info("Interview ended after %d turns (stage: %s)", self.session.turn_count, self.session.stage.value)
        return summary

    def get_assessment(self) -> "AssessmentResult":
        """Generate and persist post-interview assessment."""
        from app.assessment import AssessmentResult, generate_assessment
        from app.session_store import save_session

        result = generate_assessment(self.get_transcript(), self.session.resume_context)

        if self.session_id:
            try:
                save_session(
                    session_id=self.session_id,
                    transcript=self.get_transcript(),
                    assessment=result,
                    resume_context=self.session.resume_context,
                    turn_count=self.session.turn_count,
                    final_stage=self.session.stage.value,
                )
            except Exception as exc:
                logger.warning("Failed to save session: %s", exc)

        return result

    def _build_system_message(self) -> str:
        parts = [self._system_prompt]
        if self.session.resume_context:
            parts.append(f"\n\nCandidate Resume:\n{self.session.resume_context}")
        stage_instruction = _STAGE_INSTRUCTIONS.get(self.session.stage, "")
        parts.append(
            f"\n\nCurrent stage: {self.session.stage.value.upper()}. {stage_instruction} "
            f"(Turn {self.session.turn_count + 1} of {MAX_INTERVIEW_TURNS}.) "
            f"Reply in plain spoken sentences only. No asterisks, no bullets, no markdown."
        )
        return "\n".join(parts)

    @property
    def is_active(self) -> bool:
        return self.session.state == InterviewState.ACTIVE

    @property
    def current_stage(self) -> str:
        return self.session.stage.value

    def get_transcript(self) -> str:
        lines = []
        for t in self.session.turns:
            label = "Interviewer" if t.role == "assistant" else "Candidate"
            lines.append(f"**{label}:** {t.content}")
        return "\n\n".join(lines)
