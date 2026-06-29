from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

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
from services.gateway.app.security import require_recruiter

router = APIRouter(prefix="/candidates", tags=["candidates"])


async def _recruiter_for(db: AsyncSession, user_id: str) -> Recruiter:
    rec = await db.scalar(select(Recruiter).where(Recruiter.user_id == user_id))
    if not rec:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No recruiter profile")
    return rec


@router.delete("/{candidate_id}", status_code=204)
async def delete_candidate(
    candidate_id: str, claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> None:
    recruiter = await _recruiter_for(db, claims["sub"])
    cand = await db.get(Candidate, candidate_id)
    if not cand or cand.org_id != recruiter.org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    # Get all interviews for this candidate under this recruiter's org
    ivs = (await db.execute(
        select(Interview).where(Interview.candidate_id == cand.id)
    )).scalars().all()

    # Manually cascade delete all related interview data
    for iv in ivs:
        await db.execute(delete(Response).where(Response.interview_id == iv.id))
        await db.execute(delete(Question).where(Question.interview_id == iv.id))
        await db.execute(delete(Assessment).where(Assessment.interview_id == iv.id))
        await db.execute(delete(MeetingLink).where(MeetingLink.interview_id == iv.id))
        await db.delete(iv)

    # Delete all resumes for this candidate
    await db.execute(delete(Resume).where(Resume.candidate_id == cand.id))
    
    # Finally, delete the candidate
    await db.delete(cand)
    await db.commit()
