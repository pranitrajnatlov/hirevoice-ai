"""
Session persistence — saves interview transcripts and assessments to disk.

Each completed interview writes a single JSON file to data/sessions/.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import DATA_DIR

if TYPE_CHECKING:
    from app.assessment import AssessmentResult

logger = logging.getLogger(__name__)

SESSIONS_DIR = DATA_DIR / "sessions"


def _ensure_sessions_dir() -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def save_session(
    session_id: str,
    transcript: str,
    assessment: "AssessmentResult",
    resume_context: str = "",
    turn_count: int = 0,
    final_stage: str = "",
) -> Path:
    """
    Write interview session to data/sessions/<session_id>.json.
    Returns the path written.
    """
    _ensure_sessions_dir()
    path = SESSIONS_DIR / f"{session_id}.json"

    payload: dict[str, Any] = {
        "session_id": session_id,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "turn_count": turn_count,
        "final_stage": final_stage,
        "has_resume": bool(resume_context.strip()),
        "transcript": transcript,
        "assessment": assessment.to_dict(),
    }

    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Session saved: %s (%d turns)", path.name, turn_count)
    return path


def list_sessions() -> list[dict[str, Any]]:
    """Return metadata for all saved sessions, newest first."""
    _ensure_sessions_dir()
    sessions = []
    for p in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sessions.append({
                "session_id": data.get("session_id", p.stem),
                "completed_at": data.get("completed_at", ""),
                "turn_count": data.get("turn_count", 0),
                "recommendation": data.get("assessment", {}).get("recommendation", "?"),
                "overall_score": data.get("assessment", {}).get("overall_score", 0),
                "path": str(p),
            })
        except Exception:
            pass
    return sessions


def load_session(session_id: str) -> dict[str, Any]:
    """Load a saved session by ID."""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))
