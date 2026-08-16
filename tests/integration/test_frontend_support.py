"""Read-only endpoints that support an honest client: member identity,
household discovery, and the recipient handoff inbox.

These were added so the frontend never has to render a raw UUID for a person,
rediscover its own tenancy from client-side storage, or rely on an out-of-band
contract link. They change no ownership semantics.
"""

from __future__ import annotations

import pytest

from tests.conftest import register_user

pytestmark = pytest.mark.integration


def _household_with_two(client):
    _, owner_id, owner_h = register_user(client, "owner@example.com", name="Alice Rivera")
    hid = client.post("/v1/households", json={"name": "Rivera"}, headers=owner_h).json()["id"]
    token = client.post(f"/v1/households/{hid}/invites", json={}, headers=owner_h).json()["token"]
    _, joiner_id, joiner_h = register_user(client, "bob@example.com", name="Bob Rivera")
    client.post(f"/v1/invites/{token}/accept", headers=joiner_h)
    return hid, owner_h, joiner_h


def test_members_include_human_identity(client) -> None:
    hid, owner_h, _ = _household_with_two(client)
    members = client.get(f"/v1/households/{hid}/members", headers=owner_h).json()
    by_name = {m["display_name"]: m for m in members}
    assert set(by_name) == {"Alice Rivera", "Bob Rivera"}
    assert by_name["Alice Rivera"]["email"] == "owner@example.com"
    assert by_name["Bob Rivera"]["role"] == "member"


def test_list_my_households(client) -> None:
    _, _, owner_h = register_user(client, "a@example.com")
    h1 = client.post("/v1/households", json={"name": "Home"}, headers=owner_h).json()["id"]
    h2 = client.post("/v1/households", json={"name": "Lake House"}, headers=owner_h).json()["id"]

    listing = client.get("/v1/households", headers=owner_h)
    assert listing.status_code == 200
    ids = {h["id"] for h in listing.json()}
    assert ids == {h1, h2}


def test_list_households_is_scoped_to_membership(client) -> None:
    _, _, owner_h = register_user(client, "owner2@example.com")
    client.post("/v1/households", json={"name": "Private"}, headers=owner_h)
    _, _, stranger_h = register_user(client, "stranger@example.com")
    assert client.get("/v1/households", headers=stranger_h).json() == []


def test_incoming_handoff_inbox(client) -> None:
    hid, owner_h, joiner_h = _household_with_two(client)
    members = client.get(f"/v1/households/{hid}/members", headers=owner_h).json()
    bob_mid = next(m["id"] for m in members if m["display_name"] == "Bob Rivera")

    rid = client.post(
        f"/v1/responsibilities?household_id={hid}",
        json={
            "title": "Water the garden",
            "steps": [
                {"step_key": "execute", "kind": "execute", "description": "Water it"},
            ],
        },
        headers=owner_h,
    ).json()["id"]
    client.post(
        f"/v1/responsibilities/{rid}/handoffs",
        json={"target_membership_id": bob_mid},
        headers=owner_h,
    )

    # Bob sees the pending contract addressed to him, with human context.
    inbox = client.get("/v1/me/handoffs", headers=joiner_h)
    assert inbox.status_code == 200
    items = inbox.json()
    assert len(items) == 1
    assert items[0]["responsibility_title"] == "Water the garden"
    assert items[0]["proposer_display_name"] == "Alice Rivera"
    assert items[0]["status"] == "pending"

    # The proposer does not see it in their own inbox.
    assert client.get("/v1/me/handoffs", headers=owner_h).json() == []
