"""End-to-end: two real users perform a full responsibility handoff through the
API, then the worker delivers to the new owner. The whole manifesto flow, no
manual DB edits."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from relay.core.clock import FrozenClock
from relay.core.enums import ReminderState
from relay.core.models import Reminder
from relay.notifications.channels import InAppChannel
from relay.worker.runner import Worker
from tests.conftest import register_user

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

PAST_DUE = dt.datetime(2026, 1, 1, 9, 0, tzinfo=dt.UTC)


def test_two_users_complete_a_real_handoff(client, engine: Engine) -> None:
    # 1. Two independent users register.
    _, a_user, a = register_user(client, "alice@ex.com", name="Alice")
    _, b_user, b = register_user(client, "bob@ex.com", name="Bob")

    # 2. Alice creates a household and invites Bob, who joins.
    hid = client.post("/v1/households", json={"name": "Home"}, headers=a).json()["id"]
    token = client.post(f"/v1/households/{hid}/invites", json={}, headers=a).json()["token"]
    assert client.post(f"/v1/invites/{token}/accept", headers=b).status_code == 200

    members = client.get(f"/v1/households/{hid}/members", headers=a).json()
    a_mid = next(m["id"] for m in members if m["user_id"] == a_user)
    b_mid = next(m["id"] for m in members if m["user_id"] == b_user)

    # 3. Alice drafts from free text (AI/fallback), then creates the responsibility.
    draft = client.post(
        f"/v1/responsibilities/drafts?household_id={hid}",
        json={"text": "Take Maya to the dentist"},
        headers=a,
    )
    assert draft.status_code == 200
    assert draft.json()["steps"]  # a usable draft came back

    create = client.post(
        f"/v1/responsibilities?household_id={hid}",
        json={
            "title": "Maya dentist",
            "target_at": PAST_DUE.isoformat(),
            "steps": [{"step_key": "execute", "kind": "execute", "description": "book + attend"}],
        },
        headers=a,
    )
    assert create.status_code == 201
    resp_id = create.json()["id"]
    assert create.json()["current_owner_membership_id"] == a_mid

    # 4. Alice's ghost queue has the reminder; Bob's is empty.
    assert len(client.get("/v1/me/ghost-queue", headers=a).json()) == 1
    assert client.get("/v1/me/ghost-queue", headers=b).json() == []

    # 5. Alice proposes the handoff to Bob.
    contract_id = client.post(
        f"/v1/responsibilities/{resp_id}/handoffs",
        json={"target_membership_id": b_mid},
        headers=a,
    ).json()["id"]

    # 6. Bob independently sees and accepts the contract.
    assert client.get(f"/v1/handoffs/{contract_id}", headers=b).status_code == 200
    accept = client.post(
        f"/v1/handoffs/{contract_id}/accept",
        json={"idempotency_key": "e2e-accept"},
        headers=b,
    )
    assert accept.status_code == 200
    assert accept.json()["new_owner_membership_id"] == b_mid
    assert accept.json()["ownership_version"] == 2

    # 7. Persisted truth: Alice refreshes and is no longer owner; Bob is.
    xray = client.get(f"/v1/responsibilities/{resp_id}", headers=a).json()
    assert xray["current_owner_membership_id"] == b_mid
    assert xray["ownership_version"] == 2

    # 8. No Boomerang: the reminder now belongs to Bob, not Alice.
    assert client.get("/v1/me/ghost-queue", headers=a).json() == []
    bob_queue = client.get("/v1/me/ghost-queue", headers=b).json()
    assert len(bob_queue) == 1
    assert bob_queue[0]["responsibility_id"] == resp_id

    # 9. The worker fires the due reminder -> Bob receives an in-app notification.
    Worker(
        engine,
        "e2e",
        clock=FrozenClock(PAST_DUE + dt.timedelta(minutes=1)),
        channels=[InAppChannel()],
    ).tick()

    a_notes = client.get("/v1/me/notifications", headers=a).json()
    b_notes = client.get("/v1/me/notifications", headers=b).json()
    # Bob (the new owner) receives notifications; Alice receives nothing.
    assert len(b_notes) >= 1
    assert a_notes == []

    # 10. Proof of Relief reflects the real transfer.
    proof = client.get(f"/v1/responsibilities/{resp_id}/proof-of-relief", headers=b).json()
    assert proof["transferred"] is True
    assert proof["new_owner_membership_id"] == b_mid
    assert proof["ownership_version_after"] == 2
    assert proof["reminders_rerouted"] >= 1

    # 11. Ownership history reconstructs the story.
    history = client.get(f"/v1/responsibilities/{resp_id}/ownership-history", headers=b).json()
    event_types = [e["event_type"] for e in history]
    assert "created" in event_types
    assert "proposed" in event_types
    assert "transferred" in event_types

    # 12. Idempotent replay of the accept returns the same result, no new transfer.
    replay = client.post(
        f"/v1/handoffs/{contract_id}/accept",
        json={"idempotency_key": "e2e-accept"},
        headers=b,
    ).json()
    assert replay["replayed"] is True
    assert replay["ownership_version"] == 2

    # Verify in Postgres directly: every live reminder is owned by Bob.
    with Session(engine) as s:
        live = s.query(Reminder).filter(Reminder.state == ReminderState.scheduled).all()
        assert all(str(r.recipient_membership_id) == b_mid for r in live)
