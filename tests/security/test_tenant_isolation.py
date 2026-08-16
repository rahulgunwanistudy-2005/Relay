"""Cross-tenant isolation: every household-scoped path must fail closed for
non-members, and revoked/stale credentials must be rejected."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from relay.core.models import Membership, UserSession
from tests.conftest import register_user

pytestmark = [pytest.mark.integration, pytest.mark.security]


def _make_household(client, headers, name="H") -> str:
    return client.post("/v1/households", json={"name": name}, headers=headers).json()["id"]


def test_member_of_a_cannot_read_household_b(client) -> None:
    _, _, a = register_user(client, "a@ex.com")
    _, _, b = register_user(client, "b@ex.com")
    hb = _make_household(client, b, "B-home")

    # A is authenticated but not a member of B's household.
    assert client.get(f"/v1/households/{hb}", headers=a).status_code == 404
    assert client.get(f"/v1/households/{hb}/members", headers=a).status_code == 404
    assert client.post(f"/v1/households/{hb}/invites", json={}, headers=a).status_code == 404


def test_random_household_id_is_not_found(client) -> None:
    _, _, a = register_user(client, "a2@ex.com")
    ghost = uuid.uuid4()
    assert client.get(f"/v1/households/{ghost}", headers=a).status_code == 404


def test_revoked_membership_loses_access(client, engine: Engine) -> None:
    _, user_id, a = register_user(client, "rev@ex.com")
    hid = _make_household(client, a, "Mine")
    assert client.get(f"/v1/households/{hid}", headers=a).status_code == 200

    # Deactivate the membership directly.
    with Session(engine) as s:
        s.execute(
            update(Membership)
            .where(Membership.user_id == uuid.UUID(user_id))
            .values(is_active=False, revoked_at=dt.datetime.now(dt.UTC))
        )
        s.commit()

    assert client.get(f"/v1/households/{hid}", headers=a).status_code == 404


def test_expired_session_is_rejected(client, engine: Engine) -> None:
    token, user_id, headers = register_user(client, "exp@ex.com")
    assert client.get("/v1/me", headers=headers).status_code == 200

    with Session(engine) as s:
        s.execute(
            update(UserSession)
            .where(UserSession.user_id == uuid.UUID(user_id))
            .values(expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1))
        )
        s.commit()

    assert client.get("/v1/me", headers=headers).status_code == 401


def test_revoked_session_is_rejected(client, engine: Engine) -> None:
    _, user_id, headers = register_user(client, "revs@ex.com")
    with Session(engine) as s:
        s.execute(
            update(UserSession)
            .where(UserSession.user_id == uuid.UUID(user_id))
            .values(revoked_at=dt.datetime.now(dt.UTC))
        )
        s.commit()
    assert client.get("/v1/me", headers=headers).status_code == 401


def test_email_targeted_invite_rejects_other_user(client) -> None:
    _, _, owner = register_user(client, "owner@ex.com")
    hid = _make_household(client, owner, "Targeted")
    inv = client.post(
        f"/v1/households/{hid}/invites",
        json={"email": "intended@ex.com"},
        headers=owner,
    )
    token = inv.json()["token"]

    _, _, wrong = register_user(client, "wrong@ex.com")
    # Wrong email cannot accept a targeted invite.
    assert client.post(f"/v1/invites/{token}/accept", headers=wrong).status_code == 403


def test_forged_bearer_token_rejected(client) -> None:
    forged = {"Authorization": "Bearer " + "x" * 43}
    assert client.get("/v1/me", headers=forged).status_code == 401
