"""Shared test fixtures.

Tests run against a real Postgres (``relay_test``), never SQLite. The database
URL is forced here — before any ``relay`` import — so the module-level engine
binds to the test database.
"""

from __future__ import annotations

import os

# Force the test database before relay modules construct their engine.
os.environ.setdefault(
    "RELAY_DATABASE_URL",
    os.environ.get(
        "RELAY_TEST_DATABASE_URL",
        "postgresql://postgres@localhost:5432/relay_test",
    ),
)
os.environ["RELAY_ENVIRONMENT"] = "test"
os.environ["RELAY_LOG_JSON"] = "false"

import pytest  # noqa: E402
from sqlalchemy import Engine  # noqa: E402

from relay.db.session import engine as app_engine  # noqa: E402
from relay.models import Base  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Build the schema once for the test session, drop it after."""
    Base.metadata.drop_all(app_engine)
    Base.metadata.create_all(app_engine)
    yield
    Base.metadata.drop_all(app_engine)


@pytest.fixture
def engine() -> Engine:
    return app_engine


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from relay.api.main import create_app

    return TestClient(create_app())


def register_user(client, email: str, password: str = "correct horse battery", name: str = "U"):
    """Register a user via the API; return (token, user_id, auth_headers)."""
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    token = body["access_token"]
    return token, body["user_id"], {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_tables(engine: Engine) -> None:
    """Truncate all tables between tests for isolation."""
    yield
    from sqlalchemy import text

    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
