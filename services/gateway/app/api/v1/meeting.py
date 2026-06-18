"""Public meeting-link resolution — no auth, no candidate PII leaked."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.app.db import get_db
from services.gateway.app.models import Interview, MeetingLink
from services.gateway.app.schemas import MeetingInfo
from services.gateway.app.timeutil import aware_utc, now_utc

router = APIRouter(prefix="/meeting", tags=["meeting"])


async def resolve_link(db: AsyncSession, token: str) -> tuple[MeetingLink, Interview]:
    link = await db.scalar(select(MeetingLink).where(MeetingLink.token == token))
    if not link or link.revoked:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid meeting link")
    if aware_utc(link.expires_at) < now_utc():
        raise HTTPException(status.HTTP_410_GONE, "Meeting link expired")
    interview = await db.get(Interview, link.interview_id)
    return link, interview


@router.get("/{token}", response_model=MeetingInfo)
async def get_meeting(token: str, db: AsyncSession = Depends(get_db)) -> MeetingInfo:
    _link, interview = await resolve_link(db, token)
    return MeetingInfo(
        role_title=interview.role_title,
        duration_min=20,
        status=interview.status,
        valid=interview.status in ("invited", "in_progress"),
    )
