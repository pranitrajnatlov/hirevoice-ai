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

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.assessment import generate_assessment            # existing — unchanged
from app.resume_integration import load_resume_from_file  # existing — unchanged
from app.config import get_mode
from services.ai.app.providers.registry import PROVIDERS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hirevoice.ai")

app = FastAPI(title="HireVoice AI Service", version="1.0.0")


# ── Schemas ───────────────────────────────────────────────────────────────────
class TurnRequest(BaseModel):
    history: list[dict]            # [{role: 'assistant'|'user', content: str}]
    stage: str = "opening"         # opening|technical|behavioral|closing
    resume_context: str = ""
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


# ── Resume analysis ─────────────────────────────────────────────────────────────
@app.post("/ai/resume/analyze")
async def analyze_resume(file: UploadFile = File(...)) -> dict:
    """Extract resume text (reusing app/resume_integration) and derive a structured profile."""
    suffix = Path(file.filename or "resume.txt").suffix or ".txt"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    text = load_resume_from_file(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)

    prompt = [
        {"role": "system", "content": (
            "Extract a JSON profile from this resume with keys: name, current_role, "
            "years_experience, skills (list), domains (list), highlights (list). JSON only."
        )},
        {"role": "user", "content": text[:6000]},
    ]
    try:
        raw = PROVIDERS.llm.chat(prompt, temperature=0.1, max_tokens=600)
        profile = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        profile = {}
    return {"text": text, "profile": profile, "chars": len(text)}


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
                "Set a relaxed tone in 1-2 sentences, then ask ONE open question about their background "
                "or what drew them to this role. Sound human, not scripted."
            ),
            "max_tokens": 220,
        },
        "technical": {
            "hint": (
                "Briefly acknowledge the candidate's last answer in one short sentence if it's natural to do so, "
                "then pivot to ONE precise technical question. Pick a single skill or project from their resume "
                "and go deep — do not combine topics or ask follow-up questions in the same turn."
            ),
            "max_tokens": 180,
        },
        "behavioral": {
            "hint": (
                "Ask ONE behavioral question using the STAR framing (Situation/Task/Action/Result). "
                "Pick a real scenario — conflict resolution, ownership, a time they failed and learned. "
                "A brief 1-sentence lead-in is fine; end with exactly one question."
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
        "You are HireVoice AI — a warm, professional voice interviewer. "
        "This is a spoken conversation, so write exactly as you would speak out loud.\n\n"
        "NON-NEGOTIABLE RULES:\n"
        "- End every response with EXACTLY ONE question. Never ask two questions in the same turn.\n"
        "- Plain conversational English only. No markdown, bullets, asterisks, or numbered lists.\n"
        "- Do not recap or paraphrase what the candidate just said before asking your question.\n"
        "- React naturally to what the candidate shares — be curious, not mechanical.\n\n"
        f"Stage: {req.stage.upper()} (turn {req.turn_count + 1} of {req.max_turns}).\n"
        f"{cfg['hint']}"
    )
    if req.resume_context:
        system += f"\n\nCandidate resume — use name, skills, and projects naturally in conversation:\n{req.resume_context}"

    messages = [{"role": "system", "content": system}, *req.history]
    if not req.history:
        messages.append({"role": "user", "content": "Begin the interview now."})

    question = PROVIDERS.llm.chat(messages, temperature=0.75, max_tokens=cfg["max_tokens"])
    return TurnResponse(question=question, stage=req.stage)


# ── STT ──────────────────────────────────────────────────────────────────────────
@app.post("/ai/stt/transcribe")
async def transcribe(file: UploadFile = File(...)) -> dict:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        text = PROVIDERS.stt.transcribe(tmp_path)
        return {"text": text}
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
