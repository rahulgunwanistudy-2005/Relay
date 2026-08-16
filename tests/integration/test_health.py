from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from relay.api import health
from relay.api.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_live_always_ok(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_ok_when_db_reachable(client: TestClient) -> None:
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"


def test_ready_degraded_when_db_down(client: TestClient, monkeypatch) -> None:
    # Point the health check at an unreachable database.
    dead = create_engine("postgresql+psycopg://postgres@localhost:1/none")
    monkeypatch.setattr(health, "engine", dead)
    resp = client.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json()["database"] == "unreachable"
