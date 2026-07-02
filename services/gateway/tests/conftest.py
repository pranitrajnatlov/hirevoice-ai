"""Test fixtures for the gateway — temp SQLite DB + mocked AI service."""

from __future__ import annotations

import os

# Must be set before any gateway import (config reads env at import time).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./.pytest_gateway.db"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


class FakeAI:
    """Stand-in for the AI service — deterministic, no models loaded."""
    async def analyze_resume(self, filename, content):
        return {"text": "Senior backend engineer, Python, FastAPI.", "profile": {"skills": ["python", "fastapi"]}}

    async def interview_turn(self, payload):
        return {"question": f"({payload['stage']}) Tell me more.", "stage": payload["stage"]}

    async def transcribe(self, content):
        return "I built scalable APIs with FastAPI and Postgres."

    async def assess(self, transcript, resume_context=""):
        return {
            "overall_score": 8, "technical_score": 7, "communication_score": 8,
            "culture_fit_score": 7, "recommendation": "hire",
            "strengths": ["API design"], "weaknesses": ["caching"],
            "red_flags": [], "summary": "Strong candidate.", "raw_output": "",
        }


@pytest_asyncio.fixture
async def client():
    from services.gateway.app.main import app
    from services.gateway.app.db import engine, init_db
    from services.gateway.app.ai_client import get_ai_client

    await init_db()
    app.dependency_overrides[get_ai_client] = lambda: FakeAI()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    for f in (".pytest_gateway.db",):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
