"""Household creation, invites, and joining through the API."""

from __future__ import annotations

import pytest

from tests.conftest import register_user

pytestmark = pytest.mark.integration


def test_create_household_and_get(client) -> None:
    _, _, headers = register_user(client, "owner@example.com")
    resp = client.post(
        "/v1/households", json={"name": "Home", "timezone": "America/New_York"}, headers=headers
    )
    assert resp.status_code == 201
    hid = resp.json()["id"]

    got = client.get(f"/v1/households/{hid}", headers=headers)
    assert got.status_code == 200
    assert got.json()["timezone"] == "America/New_York"


def test_invite_and_second_user_joins(client) -> None:
    _, owner_id, owner_h = register_user(client, "o@example.com", name="Owner")
    hid = client.post("/v1/households", json={"name": "Home"}, headers=owner_h).json()["id"]

    inv = client.post(f"/v1/households/{hid}/invites", json={}, headers=owner_h)
    assert inv.status_code == 201
    token = inv.json()["token"]

    _, joiner_id, joiner_h = register_user(client, "j@example.com", name="Joiner")
    acc = client.post(f"/v1/invites/{token}/accept", headers=joiner_h)
    assert acc.status_code == 200
    assert acc.json()["household_id"] == hid

    members = client.get(f"/v1/households/{hid}/members", headers=owner_h)
    assert members.status_code == 200
    user_ids = {m["user_id"] for m in members.json()}
    assert user_ids == {owner_id, joiner_id}


def test_invite_cannot_be_used_twice(client) -> None:
    _, _, owner_h = register_user(client, "o2@example.com")
    hid = client.post("/v1/households", json={"name": "Home"}, headers=owner_h).json()["id"]
    token = client.post(f"/v1/households/{hid}/invites", json={}, headers=owner_h).json()["token"]

    _, _, j1 = register_user(client, "j1@example.com")
    assert client.post(f"/v1/invites/{token}/accept", headers=j1).status_code == 200

    _, _, j2 = register_user(client, "j2@example.com")
    replay = client.post(f"/v1/invites/{token}/accept", headers=j2)
    assert replay.status_code == 409  # invite already used


def test_non_admin_cannot_invite(client) -> None:
    _, _, owner_h = register_user(client, "o3@example.com")
    hid = client.post("/v1/households", json={"name": "Home"}, headers=owner_h).json()["id"]
    token = client.post(f"/v1/households/{hid}/invites", json={}, headers=owner_h).json()["token"]

    _, _, member_h = register_user(client, "m3@example.com")
    client.post(f"/v1/invites/{token}/accept", headers=member_h)

    # The plain member tries to invite -> forbidden (role is member, not admin).
    resp = client.post(f"/v1/households/{hid}/invites", json={}, headers=member_h)
    assert resp.status_code == 403
