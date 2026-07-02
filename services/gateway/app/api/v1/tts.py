"""TTS proxy — streams WAV audio from the AI service to the browser."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from services.gateway.app.ai_client import AIClient, get_ai_client

router = APIRouter(prefix="/tts", tags=["tts"])


class SynthRequest(BaseModel):
    text: str


@router.post("/synthesize")
async def synthesize(body: SynthRequest, ai: AIClient = Depends(get_ai_client)) -> Response:
    if not body.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "text is required")
    try:
        audio = await ai.synthesize(body.text)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"TTS unavailable: {exc}") from exc
    return Response(content=audio, media_type="audio/wav")
