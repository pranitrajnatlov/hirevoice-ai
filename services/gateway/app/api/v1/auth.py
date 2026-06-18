"""Auth router — register, login, refresh, me. (OAuth: Phase 2b — see core/oauth.py TODO.)"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.app.config import settings
from services.gateway.app.db import get_db
from services.gateway.app.models import Organization, Recruiter, RefreshToken, User
from services.gateway.app.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from services.gateway.app.security import (
    create_access_token,
    get_current_claims,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access = create_access_token(user.id, user.role)
    raw_refresh = secrets.token_urlsafe(32)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_refresh.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
    ))
    await db.commit()
    return TokenResponse(access_token=access, refresh_token=raw_refresh)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    org = Organization(name=body.org_name or f"{body.email.split('@')[0]}'s org")
    db.add(org)
    await db.flush()

    user = User(
        email=body.email, full_name=body.full_name, role="recruiter",
        password_hash=hash_password(body.password), org_id=org.id,
    )
    db.add(user)
    await db.flush()
    db.add(Recruiter(user_id=user.id, org_id=org.id))
    await db.commit()
    return await _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == body.email))
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    user.last_login_at = datetime.now(timezone.utc) if hasattr(user, "last_login_at") else None
    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = await db.scalar(select(RefreshToken).where(
        RefreshToken.token_hash == token_hash, RefreshToken.revoked == False  # noqa: E712
    ))
    from services.gateway.app.timeutil import aware_utc
    if not rt or aware_utc(rt.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")
    rt.revoked = True  # rotate
    user = await db.get(User, rt.user_id)
    return await _issue_tokens(db, user)


@router.get("/me", response_model=UserOut)
async def me(claims: dict = Depends(get_current_claims), db: AsyncSession = Depends(get_db)) -> UserOut:
    user = await db.get(User, claims["sub"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role)
