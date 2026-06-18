"""Gateway configuration (pydantic-settings, 12-factor)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Portable default (SQLite) so the gateway runs/tests without Postgres.
    # Prod: postgresql+asyncpg://user:pass@host/db
    database_url: str = "sqlite+aiosqlite:///./hirevoice.db"
    redis_url: str = "redis://localhost:6379/0"
    ai_service_url: str = "http://localhost:8800"
    s3_endpoint: str = "http://localhost:9000"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30

    meeting_link_base: str = "http://localhost:3000/interview"
    meeting_link_ttl_days: int = 7


settings = Settings()
