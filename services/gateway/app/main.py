"""
HireVoice API Gateway — FastAPI (scaffold).

Responsibilities (built out in Phase 2):
  auth (JWT + Google/Microsoft OAuth), recruiter/candidate management, interview CRUD,
  meeting links, live session lifecycle, WebSocket/Socket.IO hub, S3 presigned URLs.

This scaffold provides health + a demonstration proxy to the AI service so the
docker-compose stack is coherent end-to-end. Routers in app/api/v1/ replace the demo.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8800")

app = FastAPI(title="HireVoice API Gateway", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to web origin in prod
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateway"}


@app.get("/health/ai")
async def ai_health() -> dict:
    """Demonstrates gateway → AI service internal call. Replaced by real orchestration."""
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{AI_SERVICE_URL}/ai/health")
        return {"gateway": "ok", "ai": r.json()}


# Phase 2: include_router(auth), include_router(interviews), include_router(sessions),
#          include_router(candidates), include_router(meeting_links), include_router(analytics)
#          + Socket.IO mount for the /interview namespace.
