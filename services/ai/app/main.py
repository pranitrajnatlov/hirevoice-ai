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
    raw = PROVIDERS.llm.chat(prompt, temperature=0.1, max_tokens=600)
    try:
        profile = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        profile = {"raw": raw}
    return {"text": text, "profile": profile, "chars": len(text)}


# ── Interview turn (next question / follow-up) ───────────────────────────────────
@app.post("/ai/interview/turn", response_model=TurnResponse)
def interview_turn(req: TurnRequest) -> TurnResponse:
    """
    Stateless next-question generation. The gateway owns session state and passes the
    running history + current stage. Mirrors app/interviewer.py prompt construction.
    """
    stage_hint = {
        "opening": "Greet the candidate warmly in one sentence, then ask one brief icebreaker about their background.",
        "technical": "Ask ONE specific technical question about their experience or a concept from their resume. Pick the single most relevant topic — do not combine multiple topics.",
        "behavioral": "Ask ONE STAR-format question about a specific situation (teamwork, conflict, ownership, or learning from failure).",
        "closing": "Thank the candidate warmly and invite them to ask any questions they have.",
    }.get(req.stage, "")

    system = (
        "You are HireVoice AI conducting a VOICE interview. "
        "ABSOLUTE RULES — violating these breaks the interview:\n"
        "1. Ask EXACTLY ONE question per turn. Never combine or list multiple questions.\n"
        "2. Keep your entire response to 1-2 sentences maximum.\n"
        "3. Plain spoken English only — no markdown, no bullets, no asterisks, no numbered lists.\n"
        "4. Do not summarise what the candidate said before asking your question.\n"
        f"\nCurrent stage: {req.stage.upper()} (turn {req.turn_count + 1} of {req.max_turns}). {stage_hint}"
    )
    if req.resume_context:
        system += f"\n\nCandidate resume (use as context, do not read out loud):\n{req.resume_context}"

    messages = [{"role": "system", "content": system}, *req.history]
    if not req.history:
        messages.append({"role": "user", "content": "Begin the interview now."})

    question = PROVIDERS.llm.chat(messages, temperature=0.7, max_tokens=120)
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
