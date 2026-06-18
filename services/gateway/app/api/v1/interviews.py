"""Interviews router — create (with AI resume analysis + meeting link), list, get."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.app.ai_client import AIClient, get_ai_client
from services.gateway.app.config import settings
from services.gateway.app.db import get_db
from services.gateway.app.models import (
    Assessment,
    Candidate,
    Interview,
    MeetingLink,
    Recruiter,
    Resume,
)
from services.gateway.app.config import settings
from services.gateway.app.schemas import CreateInterviewResponse, InterviewOut
from services.gateway.app.security import require_recruiter

router = APIRouter(prefix="/interviews", tags=["interviews"])


async def _recruiter_for(db: AsyncSession, user_id: str) -> Recruiter:
    rec = await db.scalar(select(Recruiter).where(Recruiter.user_id == user_id))
    if not rec:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No recruiter profile")
    return rec


@router.post("", response_model=CreateInterviewResponse, status_code=201)
async def create_interview(
    role_title: str = Form(...),
    candidate_name: str = Form(...),
    candidate_email: str = Form(...),
    job_description: str = Form(""),
    resume: UploadFile | None = File(None),
    claims: dict = Depends(require_recruiter),
    db: AsyncSession = Depends(get_db),
    ai: AIClient = Depends(get_ai_client),
) -> CreateInterviewResponse:
    recruiter = await _recruiter_for(db, claims["sub"])

    # Candidate (upsert by email within org)
    candidate = await db.scalar(select(Candidate).where(Candidate.email == candidate_email))
    if not candidate:
        candidate = Candidate(full_name=candidate_name, email=candidate_email, org_id=recruiter.org_id)
        db.add(candidate)
        await db.flush()

    # Resume analysis via AI service
    resume_row = None
    plan = None
    if resume is not None:
        content = await resume.read()
        analysis = await ai.analyze_resume(resume.filename or "resume.pdf", content)
        resume_row = Resume(
            candidate_id=candidate.id,
            extracted_text=analysis.get("text"),
            parsed_profile=analysis.get("profile"),
        )
        db.add(resume_row)
        await db.flush()
        plan = {"focus": analysis.get("profile", {}).get("skills", []), "stages":
                ["opening", "technical", "behavioral", "closing"]}

    interview = Interview(
        org_id=recruiter.org_id, recruiter_id=recruiter.id, candidate_id=candidate.id,
        resume_id=resume_row.id if resume_row else None,
        role_title=role_title, job_description=job_description,
        interview_plan=plan, status="invited",
    )
    db.add(interview)
    await db.flush()

    link = MeetingLink(
        interview_id=interview.id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.meeting_link_ttl_days),
    )
    db.add(link)
    await db.commit()

    return CreateInterviewResponse(
        interview_id=interview.id, candidate_id=candidate.id,
        meeting_url=f"{settings.meeting_link_base}/{link.token}",
        meeting_token=link.token, status=interview.status, plan=plan,
    )


@router.get("", response_model=list[InterviewOut])
async def list_interviews(
    claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> list[InterviewOut]:
    recruiter = await _recruiter_for(db, claims["sub"])
    rows = (await db.execute(
        select(Interview, Candidate, Assessment)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .outerjoin(Assessment, Assessment.interview_id == Interview.id)
        .where(Interview.recruiter_id == recruiter.id)
        .order_by(Interview.created_at.desc())
    )).all()
    return [
        InterviewOut(
            id=iv.id, role_title=iv.role_title, status=iv.status,
            candidate_id=cand.id, candidate_name=cand.full_name, created_at=iv.created_at,
            overall_score=asmt.overall_score if asmt else None,
            recommendation=asmt.recommendation if asmt else None,
        )
        for iv, cand, asmt in rows
    ]


@router.get("/{interview_id}")
async def get_interview(
    interview_id: str, claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> dict:
    iv = await db.get(Interview, interview_id)
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    cand = await db.get(Candidate, iv.candidate_id)
    asmt = await db.scalar(select(Assessment).where(Assessment.interview_id == iv.id))
    link = await db.scalar(select(MeetingLink).where(MeetingLink.interview_id == iv.id))
    return {
        "id": iv.id, "role_title": iv.role_title, "status": iv.status,
        "job_description": iv.job_description, "plan": iv.interview_plan,
        "meeting_token": link.token if link else None,
        "meeting_url": f"{settings.meeting_link_base}/{link.token}" if link else None,
        "candidate": {"id": cand.id, "name": cand.full_name, "email": cand.email},
        "assessment": {
            "overall_score": asmt.overall_score, "recommendation": asmt.recommendation,
            "strengths": asmt.strengths, "weaknesses": asmt.weaknesses, "summary": asmt.summary,
            "technical_score": asmt.technical_score,
            "communication_score": asmt.communication_score,
            "culture_fit_score": asmt.culture_fit_score,
        } if asmt else None,
    }
