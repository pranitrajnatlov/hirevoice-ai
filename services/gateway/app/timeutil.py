"""Timezone helpers — SQLite returns naive datetimes; normalize to aware UTC for comparisons."""

from __future__ import annotations

from datetime import datetime, timezone


def aware_utc(dt: datetime) -> datetime:
    """Attach UTC tzinfo if the datetime is naive (e.g. read back from SQLite)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
