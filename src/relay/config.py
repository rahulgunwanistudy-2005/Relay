"""Typed, environment-driven configuration.

All configuration loads here and nowhere else. No module reads ``os.environ``
directly. Missing or insecure required values fail fast at construction time so
a misconfigured process never silently boots with development defaults in
production.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import PostgresDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-insecure-secret-change-me"


class Environment(StrEnum):
    development = "development"
    test = "test"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RELAY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.development

    # Postgres is authoritative. Required in every environment.
    database_url: PostgresDsn

    # Session/token signing key. Must be overridden in production.
    secret_key: str = _DEV_SECRET

    log_level: str = "INFO"
    log_json: bool = True

    # Security hardening.
    cors_origins: list[str] = ["http://localhost:3000"]
    max_body_bytes: int = 1_000_000
    rate_limit_per_minute: int = 300

    # Worker cadence / leasing (seconds).
    worker_poll_interval_s: float = 1.0
    worker_lease_seconds: int = 60
    worker_heartbeat_seconds: int = 5
    worker_max_attempts: int = 5
    worker_batch_size: int = 100
    worker_retry_backoff_s: float = 30.0

    # AI extraction. Falls back to the deterministic provider when the key is unset.
    ai_provider: str = "groq"  # "groq" | "fallback"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    ai_timeout_s: float = 20.0

    # Notifications.
    deep_link_base: str = "http://localhost:3000"
    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 1025  # Mailpit default
    smtp_from: str = "relay@example.com"
    smtp_username: str | None = None
    smtp_password: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.production

    @property
    def sync_database_url(self) -> str:
        """SQLAlchemy URL using the psycopg (v3) driver."""
        url = str(self.database_url)
        if url.startswith("postgresql+"):
            return url
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> Settings:
        if self.is_production and (self.secret_key == _DEV_SECRET or len(self.secret_key) < 32):
            raise ValueError(
                "RELAY_SECRET_KEY must be set to a strong (>=32 char) value in production"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
