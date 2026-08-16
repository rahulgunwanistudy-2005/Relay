"""No Boomerang — the flagship invariant, enforced against real Postgres.

After an accepted transfer A -> B, every future Relay-generated reminder for that
responsibility resolves to B. The previous owner, the creator, and mere viewers
are never implicit recipients. The only exception is an explicitly configured
backup policy whose condition has occurred.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from relay.core.application import handoff
from relay.core.enums import ReminderState, ReminderType, ResponsibilityStatus
from relay.core.models import Reminder, Responsibility, ResponsibilityCycle
from relay.core.policies import resolve_escalation_recipient
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.security]


@pytest.fixture
def household(engine: Engine):
    with Session(engine) as s:
        hh = make_household(s)
        a = make_membership(s, make_user(s, name="A"), hh)
        b = make_membership(s, make_user(s, name="B"), hh)
        c = make_membership(s, make_user(s, name="C"), hh)
        resp = make_responsibility(s, hh, a, owner=a, status=ResponsibilityStatus.active)
        cycle = ResponsibilityCycle(responsibility_id=resp.id, sequence=1)
        s.add(cycle)
        s.flush()
        _seed_reminder(s, resp.id, cycle.id, a.id, version=1, key="seed-v1")
        s.commit()
        return {"a": a.id, "b": b.id, "c": c.id, "resp": resp.id, "cycle": cycle.id}


def _seed_reminder(s, resp_id, cycle_id, owner_id, *, version, key) -> None:
    s.add(
        Reminder(
            responsibility_id=resp_id,
            cycle_id=cycle_id,
            recipient_membership_id=owner_id,
            ownership_version=version,
            reminder_type=ReminderType.cycle_due,
            scheduled_for=dt.datetime(2026, 12, 1, 9, 0, tzinfo=dt.UTC),
            state=ReminderState.scheduled,
            dedupe_key=key,
        )
    )


def _scheduled_recipients(engine: Engine, resp_id: uuid.UUID) -> set[uuid.UUID]:
    with Session(engine) as s:
        rows = (
            s.execute(
                select(Reminder.recipient_membership_id).where(
                    Reminder.responsibility_id == resp_id,
                    Reminder.state == ReminderState.scheduled,
                )
            )
            .scalars()
            .all()
        )
        return set(rows)


def _transfer(engine: Engine, resp_id, source, target, key) -> None:
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=source,
            responsibility_id=resp_id,
            target_membership_id=target,
        ).id
        s.commit()
    with Session(engine) as s:
        handoff.accept_handoff(s, actor_membership_id=target, contract_id=cid, idempotency_key=key)
        s.commit()


def test_after_transfer_all_reminders_belong_to_new_owner(engine: Engine, household) -> None:
    assert _scheduled_recipients(engine, household["resp"]) == {household["a"]}
    _transfer(engine, household["resp"], household["a"], household["b"], "nb-1")
    # No Boomerang: only B, never A.
    assert _scheduled_recipients(engine, household["resp"]) == {household["b"]}


def test_chain_transfer_reminders_follow_to_final_owner(engine: Engine, household) -> None:
    _transfer(engine, household["resp"], household["a"], household["b"], "nb-2")
    _transfer(engine, household["resp"], household["b"], household["c"], "nb-3")
    assert _scheduled_recipients(engine, household["resp"]) == {household["c"]}

    with Session(engine) as s:
        resp = s.get(Responsibility, household["resp"])
        assert resp.current_owner_membership_id == household["c"]
        assert resp.ownership_version == 3


def test_declined_transfer_leaves_reminders_with_original_owner(engine: Engine, household) -> None:
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=household["a"],
            responsibility_id=household["resp"],
            target_membership_id=household["b"],
        ).id
        s.commit()
    with Session(engine) as s:
        handoff.decline_handoff(s, actor_membership_id=household["b"], contract_id=cid)
        s.commit()
    # Nothing rerouted: A keeps the reminder.
    assert _scheduled_recipients(engine, household["resp"]) == {household["a"]}


def test_creator_and_previous_owner_are_not_implicit_recipients(engine: Engine, household) -> None:
    # A both created and originally owned the responsibility.
    _transfer(engine, household["resp"], household["a"], household["b"], "nb-4")
    recipients = _scheduled_recipients(engine, household["resp"])
    assert household["a"] not in recipients  # creator + previous owner: nothing
    assert recipients == {household["b"]}


def test_previous_owner_only_returns_via_explicit_escalation(engine: Engine, household) -> None:
    a = household["a"]
    # With no backup policy, the previous owner is never resurrected.
    assert resolve_escalation_recipient({}, condition="overdue") is None
    # Only an explicit policy naming A brings A back, and only on its condition.
    policy = {"escalate_to": str(a), "on": ["overdue"]}
    assert resolve_escalation_recipient(policy, condition="overdue") == a
    assert resolve_escalation_recipient(policy, condition="snoozed") is None
