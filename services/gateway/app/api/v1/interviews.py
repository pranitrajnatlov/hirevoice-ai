"""Interviews router — create (with AI resume analysis + meeting link), list, get."""

from __future__ import annotations

import json
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
    Question,
    Recruiter,
    Response,
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

    # Resume analysis via AI service (best-effort: never block interview creation)
    resume_row = None
    plan = None
    if resume is not None:
        try:
            from app.interview_context import build_interview_context, infer_experience_level
            content = await resume.read()
            analysis = await ai.analyze_resume(resume.filename or "resume.pdf", content)
            profile = analysis.get("profile") or {}
            # Inject the authoritative candidate name (the parser can mis-read it from
            # flattened text, causing the AI to greet the wrong name).
            profile.setdefault("personal_information", {})
            profile["personal_information"]["name"] = {"value": candidate_name, "confidence": 1.0}

            resume_row = Resume(
                candidate_id=candidate.id,
                extracted_text=analysis.get("text"),
                parsed_profile=profile,
            )
            db.add(resume_row)
            await db.flush()
            skills = [s.get("value") if isinstance(s, dict) else s for s in (profile.get("skills") or [])]
            # Cache vocabulary + structured context (rebuilt with the correct name) once (spec #17).
            plan = {
                "focus": [s for s in skills if s],
                "vocabulary": analysis.get("vocabulary", []),
                "context": build_interview_context(profile),
                "experience_level": infer_experience_level(profile),
                "stages": ["opening", "experience", "technical", "behavioral", "closing"],
            }
        except Exception:
            pass  # Interview proceeds; AI questions won't be resume-tailored

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
            candidate_id=cand.id, candidate_name=cand.full_name, candidate_email=cand.email,
            created_at=iv.created_at,
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

    assessment = None
    if asmt:
        # raw_output holds the full assessment JSON (evidence + extra dimensions, spec #13)
        full: dict = {}
        if asmt.raw_output:
            try:
                full = json.loads(asmt.raw_output)
            except Exception:
                full = {}
        assessment = {
            "overall_score": asmt.overall_score, "recommendation": asmt.recommendation,
            "strengths": asmt.strengths, "weaknesses": asmt.weaknesses, "summary": asmt.summary,
            "technical_score": asmt.technical_score,
            "communication_score": asmt.communication_score,
            "culture_fit_score": asmt.culture_fit_score,
            "problem_solving_score": full.get("problem_solving_score"),
            "experience_relevance_score": full.get("experience_relevance_score"),
            "confidence_score": full.get("confidence_score"),
            "resume_consistency_score": full.get("resume_consistency_score"),
            "evidence": full.get("evidence", {}),
            "unsupported_scores": full.get("unsupported_scores", []),
        }

    return {
        "id": iv.id, "role_title": iv.role_title, "status": iv.status,
        "job_description": iv.job_description, "plan": iv.interview_plan,
        "meeting_token": link.token if link else None,
        "meeting_url": f"{settings.meeting_link_base}/{link.token}" if link else None,
        "candidate": {"id": cand.id, "name": cand.full_name, "email": cand.email},
        "resume_profile": (await _resume_profile(db, iv)),
        "assessment": assessment,
    }


async def _resume_profile(db: AsyncSession, iv: Interview) -> dict | None:
    """Surface the structured resume profile (with confidences) for the recruiter UI."""
    if not iv.resume_id:
        return None
    resume = await db.get(Resume, iv.resume_id)
    return resume.parsed_profile if resume else None


@router.get("/{interview_id}/ai-context")
async def get_ai_context(
    interview_id: str, claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> dict:
    """Sanitized, structured view of the resume context + interview plan the AI used."""
    from app.interview_context import build_ai_context_view

    iv = await db.get(Interview, interview_id)
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    profile = await _resume_profile(db, iv) or {}
    plan = iv.interview_plan if isinstance(iv.interview_plan, dict) else {}
    return build_ai_context_view(profile, plan, iv.role_title)


@router.get("/{interview_id}/transcript")
async def get_transcript(
    interview_id: str, claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> dict:
    """Ordered interview transcript (interviewer questions + candidate answers) for the viewer."""
    iv = await db.get(Interview, interview_id)
    if not iv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")

    questions = (await db.execute(
        select(Question).where(Question.interview_id == interview_id).order_by(Question.seq)
    )).scalars().all()
    responses = {
        r.question_id: r for r in (await db.execute(
            select(Response).where(Response.interview_id == interview_id)
        )).scalars().all()
    }

    turns: list[dict] = []
    for q in questions:
        turns.append({
            "role": "interviewer", "text": q.text, "stage": q.stage,
            "is_followup": q.is_followup,
            "ts": q.asked_at.isoformat() if q.asked_at else None,
        })
        resp = responses.get(q.id)
        if resp and resp.transcript_text:
            turns.append({
                "role": "candidate", "text": resp.transcript_text, "stage": q.stage,
                "is_followup": False,
                "ts": resp.created_at.isoformat() if resp.created_at else None,
            })
    return {"interview_id": interview_id, "turns": turns}
