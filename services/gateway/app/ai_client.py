"""Async HTTP client for the internal AI Service (services/ai)."""

from __future__ import annotations

import httpx

from services.gateway.app.config import settings


class AIClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ai_service_url).rstrip("/")

    async def analyze_resume(self, filename: str, content: bytes) -> dict:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{self.base_url}/ai/resume/analyze",
                files={"file": (filename, content)},
            )
            r.raise_for_status()
            return r.json()

    async def interview_turn(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{self.base_url}/ai/interview/turn", json=payload)
            r.raise_for_status()
            return r.json()

    async def transcribe(self, content: bytes) -> str:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{self.base_url}/ai/stt/transcribe", files={"file": ("a.wav", content)})
            r.raise_for_status()
            return r.json()["text"]

    async def assess(self, transcript: str, resume_context: str = "") -> dict:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.post(
                f"{self.base_url}/ai/assess",
                json={"transcript": transcript, "resume_context": resume_context},
            )
            r.raise_for_status()
            return r.json()


# Default instance; overridable in tests via dependency override.
ai_client = AIClient()


def get_ai_client() -> AIClient:
    return ai_client
