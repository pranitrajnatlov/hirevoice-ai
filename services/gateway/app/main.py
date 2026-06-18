"""
HireVoice API Gateway — FastAPI (scaffold).

Responsibilities (built out in Phase 2):
  auth (JWT + Google/Microsoft OAuth), recruiter/candidate management, interview CRUD,
  meeting links, live session lifecycle, WebSocket/Socket.IO hub, S3 presigned URLs.

This scaffold provides health + a demonstration proxy to the AI service so the
docker-compose stack is coherent end-to-end. Routers in app/api/v1/ replace the demo.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Make the repo root importable (so `services.*` resolves when run from anywhere).
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from services.gateway.app.config import settings
from services.gateway.app.db import init_db
from services.gateway.app.api.v1 import analytics, auth, interviews, meeting, sessions
from services.gateway.app.ws.manager import manager as ws_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()       # dev/test convenience; prod uses Alembic
    yield


app = FastAPI(title="HireVoice API Gateway", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to web origin in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(interviews.router, prefix=API)
app.include_router(meeting.router, prefix=API)
app.include_router(sessions.router, prefix=API)
app.include_router(analytics.router, prefix=API)


@app.websocket("/api/v1/ws/{interview_id}")
async def interview_ws(interview_id: str, ws: WebSocket) -> None:
    """Candidate connects here to receive real-time transcript/question events."""
    await ws_manager.connect(interview_id, ws)
    try:
        while True:
            await ws.receive_text()   # keep-alive; client may send pings
    except WebSocketDisconnect:
        ws_manager.disconnect(interview_id, ws)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gateway"}


@app.get("/health/ai")
async def ai_health() -> dict:
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{settings.ai_service_url}/ai/health")
        return {"gateway": "ok", "ai": r.json()}
