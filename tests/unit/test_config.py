from __future__ import annotations

import pytest
from pydantic import ValidationError

from relay.config import Environment, Settings


def _settings(**overrides) -> Settings:
    base = {
        "environment": "production",
        "database_url": "postgresql://u:p@localhost:5432/relay",
        "secret_key": "x" * 40,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_production_rejects_dev_secret() -> None:
    with pytest.raises(ValidationError):
        _settings(secret_key="dev-insecure-secret-change-me")


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError):
        _settings(secret_key="short")


def test_production_accepts_strong_secret() -> None:
    s = _settings()
    assert s.is_production
    assert s.environment is Environment.production


def test_development_allows_default_secret() -> None:
    s = Settings(  # type: ignore[call-arg]
        environment="development",
        database_url="postgresql://u:p@localhost:5432/relay",
    )
    assert not s.is_production


def test_sync_url_uses_psycopg_driver() -> None:
    s = Settings(  # type: ignore[call-arg]
        environment="development",
        database_url="postgresql://u:p@localhost:5432/relay",
    )
    assert s.sync_database_url.startswith("postgresql+psycopg://")
