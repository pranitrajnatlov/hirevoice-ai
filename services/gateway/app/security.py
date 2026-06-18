"""Password hashing (PBKDF2, stdlib) + JWT issue/verify + RBAC dependency."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.gateway.app.config import settings

_PBKDF2_ROUNDS = 200_000
bearer = HTTPBearer(auto_error=False)


# ── Passwords ────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, rounds, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────
def create_access_token(sub: str, role: str, *, scope: str = "user", extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub, "role": role, "scope": scope,
        "iat": now, "exp": now + timedelta(minutes=settings.access_token_ttl_min),
        **(extra or {}),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ── Dependencies ───────────────────────────────────────────────────────────────
def get_current_claims(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc


def require_recruiter(claims: dict = Depends(get_current_claims)) -> dict:
    if claims.get("role") not in ("recruiter", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Recruiter role required")
    return claims
