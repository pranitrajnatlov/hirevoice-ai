"""Pydantic request/response schemas for the gateway API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


# ── Auth ───────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    org_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    role: str


# ── Interviews ──────────────────────────────────────────────────────────────────
class CreateInterviewResponse(BaseModel):
    interview_id: str
    candidate_id: str
    meeting_url: str
    meeting_token: str
    status: str
    plan: dict | None = None


class InterviewOut(BaseModel):
    id: str
    role_title: str
    status: str
    candidate_id: str
    candidate_name: str
    candidate_email: str | None = None
    created_at: datetime
    overall_score: int | None = None
    recommendation: str | None = None


class MeetingInfo(BaseModel):
    role_title: str
    duration_min: int
    status: str
    valid: bool


# ── Sessions (candidate, token-scoped) ────────────────────────────────────────────
class SessionStartResponse(BaseModel):
    session_token: str
    interview_id: str
    question: str
    stage: str
    question_index: int
    total_estimated: int


class AnswerResponse(BaseModel):
    transcript: str
    question: str
    stage: str
    question_index: int
    completed: bool


class AssessmentOut(BaseModel):
    overall_score: int
    technical_score: int
    communication_score: int
    confidence_score: int | None = None
    culture_fit_score: int | None = None
    recommendation: str
    strengths: list[str]
    weaknesses: list[str]
    summary: str
