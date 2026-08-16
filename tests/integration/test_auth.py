"""Authentication flow through the real API + Postgres."""

from __future__ import annotations

import pytest

from tests.conftest import register_user

pytestmark = pytest.mark.integration


def test_register_login_me_logout(client) -> None:
    token, user_id, headers = register_user(client, "alice@example.com", name="Alice")

    me = client.get("/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    assert me.json()["id"] == user_id

    login = client.post(
        "/v1/auth/login",
        json={"email": "alice@example.com", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    out = client.post("/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    # Token no longer works after logout.
    assert client.get("/v1/me", headers=headers).status_code == 401


def test_duplicate_email_conflicts(client) -> None:
    register_user(client, "dup@example.com")
    resp = client.post(
        "/v1/auth/register",
        json={"email": "dup@example.com", "password": "another password!", "display_name": "X"},
    )
    assert resp.status_code == 409


def test_wrong_password_rejected(client) -> None:
    register_user(client, "bob@example.com")
    resp = client.post(
        "/v1/auth/login",
        json={"email": "bob@example.com", "password": "wrong password here"},
    )
    assert resp.status_code == 401


def test_login_unknown_user_rejected(client) -> None:
    resp = client.post(
        "/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever password"},
    )
    assert resp.status_code == 401


def test_protected_route_requires_token(client) -> None:
    assert client.get("/v1/me").status_code == 401
    assert client.get("/v1/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_short_password_rejected_by_schema(client) -> None:
    resp = client.post(
        "/v1/auth/register",
        json={"email": "shorty@example.com", "password": "short", "display_name": "S"},
    )
    assert resp.status_code == 422
