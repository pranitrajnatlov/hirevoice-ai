"""
Resume AI integration — Phase 2 stub.

Provides hooks to load resume context from the user's existing Resume AI agent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def load_resume_from_file(path: str | Path) -> str:
    """Extract text from a resume file (PDF, DOCX, or plain text)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Resume not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8")
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in (".docx", ".doc"):
        return _extract_docx(path)

    return path.read_text(encoding="utf-8", errors="replace")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        logger.warning("pypdf not installed — returning filename only")
        return f"[PDF resume: {path.name}]"


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        logger.warning("python-docx not installed — returning filename only")
        return f"[DOCX resume: {path.name}]"


def load_resume_from_resume_ai(candidate_id: Optional[str] = None) -> str:
    """
    Integration point for the existing Resume AI agent.

    Phase 2: wire this to the actual Resume AI API or database.
    """
    if candidate_id:
        logger.info("Resume AI lookup for candidate: %s (not yet implemented)", candidate_id)
    return ""