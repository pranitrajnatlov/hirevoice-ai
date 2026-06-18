"""Analytics router — recruiter dashboard KPIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.app.db import get_db
from services.gateway.app.models import Assessment, Candidate, Interview, Recruiter
from services.gateway.app.security import require_recruiter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
async def overview(
    claims: dict = Depends(require_recruiter), db: AsyncSession = Depends(get_db),
) -> dict:
    recruiter = await db.scalar(select(Recruiter).where(Recruiter.user_id == claims["sub"]))
    org_id = recruiter.org_id if recruiter else None

    total_interviews = await db.scalar(
        select(func.count()).select_from(Interview).where(Interview.org_id == org_id)
    ) or 0
    total_candidates = await db.scalar(
        select(func.count()).select_from(Candidate).where(Candidate.org_id == org_id)
    ) or 0
    avg_score = await db.scalar(
        select(func.avg(Assessment.overall_score))
        .join(Interview, Interview.id == Assessment.interview_id)
        .where(Interview.org_id == org_id)
    )
    recommended = await db.scalar(
        select(func.count()).select_from(Assessment)
        .join(Interview, Interview.id == Assessment.interview_id)
        .where(Interview.org_id == org_id, Assessment.recommendation.in_(("strong_hire", "hire")))
    ) or 0
    completed = await db.scalar(
        select(func.count()).select_from(Interview)
        .where(Interview.org_id == org_id, Interview.status == "completed")
    ) or 0

    conversion = round((recommended / completed) * 100, 1) if completed else 0.0
    return {
        "total_interviews": total_interviews,
        "total_candidates": total_candidates,
        "average_score": round(float(avg_score), 1) if avg_score is not None else None,
        "recommended_hires": recommended,
        "completed": completed,
        "conversion_rate": conversion,
    }
