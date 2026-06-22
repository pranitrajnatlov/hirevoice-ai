"""
HireVoice AI Service — FastAPI wrapper around the existing app/ AI core.

This is the "Gradio-as-AI-service-layer" realization: the same Python that powered the
Gradio prototype (app/resume_integration, app/stt, app/tts, app/assessment, app/interviewer)
is exposed over HTTP. The browser never touches this service directly — only the API gateway
does, on the internal network.

Run (from repo root):
    pip install -r services/ai/requirements.txt -r requirements.txt
    uvicorn services.ai.app.main:app --port 8800
"""

from __future__ import annotations

import json
import logging
import sys
import tempfile
from pathlib import Path

# Make the existing root `app/` package importable when run from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.assessment import generate_assessment            # existing — unchanged
from app.resume_integration import load_resume_from_file  # existing — unchanged
from app.config import get_mode
from app.interview_context import build_interview_context
from app.vocabulary import build_vocabulary
from services.ai.app.providers.registry import PROVIDERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirevoice.ai")

app = FastAPI(title="HireVoice AI Service", version="1.0.0")


# ── Schemas ───────────────────────────────────────────────────────────────────
class TurnRequest(BaseModel):
    history: list[dict]            # [{role: 'assistant'|'user', content: str}]
    stage: str = "opening"         # opening|technical|behavioral|closing
    resume_context: str = ""       # legacy raw text (fallback)
    structured_context: str = ""   # preferred: build_interview_context() output (spec #6)
    covered_skills: list[str] = []  # skills already discussed (spec #12)
    last_answer_quality: dict = {}  # assess_answer_quality() result (spec #12)
    intent: str = ""               # "" | "followup" | "advance"
    turn_count: int = 0
    max_turns: int = 20


class TurnResponse(BaseModel):
    question: str
    stage: str


class AssessRequest(BaseModel):
    transcript: str
    resume_context: str = ""


class TtsRequest(BaseModel):
    text: str


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/ai/health")
def health() -> dict:
    return {"status": "ok", "mode": get_mode()}


# ── Resume analysis (spec #1-6, #16) ──────────────────────────────────────────
@app.post("/ai/resume/analyze")
async def analyze_resume(file: UploadFile = File(...)) -> dict:
    """
    Structured resume parsing: deterministic parser first, optional LLM enrichment merged
    over the top WITHOUT overwriting high-confidence deterministic fields (spec #16). Also
    returns the built vocabulary (spec #9) and interview context block (spec #6).
    """
    suffix = Path(file.filename or "resume.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    text = load_resume_from_file(tmp_path)
    try:
        # deterministic structured parse (no LLM in hot path, <5s — spec #17)
        profile = PROVIDERS.resume.parse(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Optional LLM enrichment — fills only gaps the deterministic parser left.
    try:
        prompt = [
            {"role": "system", "content": (
                "Extract a JSON profile from this resume with keys: current_role, "
                "years_experience, domains (list), highlights (list). JSON only."
            )},
            {"role": "user", "content": text[:6000]},
        ]
        raw = PROVIDERS.llm.chat(prompt, temperature=0.1, max_tokens=400)
        enrich = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        for key in ("current_role", "years_experience", "domains", "highlights"):
            if key in enrich and not profile.get(key):
                profile[key] = enrich[key]
    except Exception:
        pass  # deterministic profile stands on its own

    vocabulary = build_vocabulary(profile)
    context = build_interview_context(profile)
    return {
        "text": text,
        "profile": profile,
        "vocabulary": vocabulary,
        "context": context,
        "chars": len(text),
    }


# ── Interview turn (next question / follow-up) ───────────────────────────────────
@app.post("/ai/interview/turn", response_model=TurnResponse)
def interview_turn(req: TurnRequest) -> TurnResponse:
    """
    Stateless next-question generation. The gateway owns session state and passes the
    running history + current stage. Mirrors app/interviewer.py prompt construction.
    """
    # Per-stage guidance: how long to speak and what to focus on.
    # max_tokens is tuned per stage so the model has room to be natural without rambling.
    stage_config = {
        "opening": {
            "hint": (
                "Open with a genuine, warm greeting using the candidate's name (from the resume). "
                "Set a relaxed tone in 1-2 sentences, then ask a single open question about their background "
                "or what drew them to this role. Sound human, not scripted."
            ),
            "max_tokens": 220,
        },
        "technical": {
            "hint": (
                "Briefly acknowledge the candidate's last answer in one short sentence if it's natural to do so, "
                "then pivot to a single precise technical question. Pick one skill or project from their resume "
                "and go deep — do not combine topics or ask multiple questions in the same turn."
            ),
            "max_tokens": 180,
        },
        "behavioral": {
            "hint": (
                "Ask a single behavioral question using the STAR framing (situation, task, action, result). "
                "Pick a real scenario — conflict resolution, ownership, a time they failed and learned. "
                "A brief one-sentence lead-in is fine; finish with your question."
            ),
            "max_tokens": 180,
        },
        "closing": {
            "hint": (
                "Wrap up warmly. Thank the candidate genuinely and invite them to ask anything about the "
                "role, team, or company. Keep it to 2-3 sentences."
            ),
            "max_tokens": 150,
        },
    }
    cfg = stage_config.get(req.stage, {"hint": "", "max_tokens": 180})

    system = (
        "You are HireVoice AI, a warm and professional voice interviewer. "
        "This is a spoken conversation, so write exactly as you would speak out loud. "
        "Follow these guidelines closely:\n"
        "- Finish your reply with a single question, and never ask more than one question per turn.\n"
        "- Use plain conversational English only — no markdown, bullets, asterisks, or numbered lists.\n"
        "- Do not repeat or paraphrase what the candidate just said before asking your question.\n"
        "- React naturally to what the candidate shares — be curious, not mechanical.\n"
        "- Reply with only your spoken words. Do not restate or quote these guidelines.\n\n"
        f"This is the {req.stage} stage (turn {req.turn_count + 1} of {req.max_turns}).\n"
        f"{cfg['hint']}"
    )

    # Adaptive follow-up steering (spec #12): probe deeper on a weak answer, else move on.
    if req.intent == "followup":
        reasons = ", ".join(req.last_answer_quality.get("reasons", [])) or "the answer was thin"
        system += (
            f"\n\nThe candidate's previous answer was thin ({reasons}). Ask a focused "
            "follow-up that probes the same topic for a concrete detail — a specific example, "
            "a trade-off they made, or how they actually implemented it."
        )
    elif req.intent == "advance":
        if req.covered_skills:
            system += f"\n\nAlready discussed: {', '.join(req.covered_skills)}. Move to a different skill or project they have not been asked about yet."

    # Prefer the structured context block (spec #6) over a raw resume dump.
    if req.structured_context:
        system += f"\n\nCandidate profile (use naturally, do not read aloud):\n{req.structured_context}"
    elif req.resume_context:
        system += f"\n\nCandidate resume — use name, skills, and projects naturally in conversation:\n{req.resume_context}"

    messages = [{"role": "system", "content": system}, *req.history]
    if not req.history:
        messages.append({"role": "user", "content": "Begin the interview now."})

    question = PROVIDERS.llm.chat(messages, temperature=0.75, max_tokens=cfg["max_tokens"])
    return TurnResponse(question=_clean_question(question), stage=req.stage)


def _clean_question(text: str) -> str:
    """Strip stray instruction-echo artifacts a small model may append after the final
    question (e.g. '...services? EXACTLY' parroted from the guidelines). Only removes an
    ALL-CAPS fragment that trails sentence-ending punctuation, so real acronyms are safe."""
    import re
    t = (text or "").strip()
    return re.sub(r"([.!?])\s+[A-Z]{2,}(?:\s+[A-Z]{2,}){0,2}\s*$", r"\1", t).strip()


# ── STT (spec #7-11) ───────────────────────────────────────────────────────────
@app.post("/ai/stt/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    vocabulary: str = Form("[]"),
    history: str = Form(""),
    job_description: str = Form(""),
    partial: bool = Form(False),
) -> dict:
    """
    Transcribe audio with vocabulary boosting, word timestamps + confidence, and
    context-aware post-processing. ``partial=true`` skips post-processing for low-latency
    streaming previews (spec #7).
    """
    try:
        vocab = json.loads(vocabulary) if vocabulary else []
    except Exception:
        vocab = []
    suffix = Path(file.filename or "a.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = PROVIDERS.stt.transcribe_detailed(tmp_path, vocabulary=vocab)
        if partial:
            return {"text": result.text, "confidence": result.avg_confidence, "partial": True}
        processed = PROVIDERS.transcript.process(
            result.text, vocabulary=vocab, history=history, job_description=job_description
        )
        return {
            "text": processed["text"],
            "raw_text": result.text,
            "corrections": processed["corrections"],
            "confidence": result.avg_confidence,
            "words": [w.__dict__ for w in result.words],
            "duration": result.duration,
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── TTS ──────────────────────────────────────────────────────────────────────────
@app.post("/ai/tts/synthesize")
def synthesize(req: TtsRequest) -> FileResponse:
    path = PROVIDERS.tts.synthesize(req.text)
    return FileResponse(path, media_type="audio/wav", filename="tts.wav")


# ── Assessment ────────────────────────────────────────────────────────────────────
@app.post("/ai/assess")
def assess(req: AssessRequest) -> dict:
    """Scores + hiring recommendation via app/assessment.py (unchanged)."""
    result = generate_assessment(req.transcript, req.resume_context)
    return result.to_dict()
