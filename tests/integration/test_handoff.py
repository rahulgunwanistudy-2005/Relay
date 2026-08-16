"""Atomic handoff — the core transaction — against real Postgres."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from relay.core.application import handoff
from relay.core.application.errors import NotAuthorized, StaleContract
from relay.core.enums import (
    OwnershipEventType,
    ReminderState,
    ReminderType,
    ResponsibilityStatus,
)
from relay.core.models import (
    OwnershipEvent,
    Reminder,
    Responsibility,
)
from relay.core.models.outbox import OutboxEvent
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = pytest.mark.integration


@pytest.fixture
def scenario(engine: Engine):
    """Household with owner A and member B, one active responsibility owned by A."""
    with Session(engine) as s:
        hh = make_household(s)
        a = make_membership(s, make_user(s, name="A"), hh)
        b = make_membership(s, make_user(s, name="B"), hh)
        resp = make_responsibility(s, hh, a, owner=a, status=ResponsibilityStatus.active)
        s.commit()
        return {
            "household_id": hh.id,
            "a": a.id,
            "b": b.id,
            "resp": resp.id,
        }


def test_propose_then_accept_transfers_ownership(engine: Engine, scenario) -> None:
    with Session(engine) as s:
        contract = handoff.propose_handoff(
            s,
            actor_membership_id=scenario["a"],
            responsibility_id=scenario["resp"],
            target_membership_id=scenario["b"],
        )
        contract_id = contract.id
        s.commit()

    with Session(engine) as s:
        resp = s.get(Responsibility, scenario["resp"])
        assert resp.status is ResponsibilityStatus.transfer_pending
        assert resp.current_owner_membership_id == scenario["a"]

    with Session(engine) as s:
        result = handoff.accept_handoff(
            s,
            actor_membership_id=scenario["b"],
            contract_id=contract_id,
            idempotency_key="idem-1",
        )
        s.commit()
        assert result.new_owner_membership_id == scenario["b"]
        assert result.ownership_version == 2
        assert not result.replayed

    with Session(engine) as s:
        resp = s.get(Responsibility, scenario["resp"])
        assert resp.status is ResponsibilityStatus.active
        assert resp.current_owner_membership_id == scenario["b"]  # No Boomerang
        assert resp.ownership_version == 2

        events = (
            s.execute(
                select(OwnershipEvent.event_type).where(
                    OwnershipEvent.responsibility_id == scenario["resp"]
                )
            )
            .scalars()
            .all()
        )
        assert OwnershipEventType.transferred in events

        outbox = s.execute(select(func.count()).select_from(OutboxEvent)).scalar_one()
        assert outbox == 1


def test_accept_reroutes_scheduled_reminders(engine: Engine, scenario) -> None:
    # Give A a scheduled reminder at ownership version 1.
    with Session(engine) as s:
        resp = s.get(Responsibility, scenario["resp"])
        cycle_id = _make_cycle(s, resp)
        s.add(
            Reminder(
                responsibility_id=resp.id,
                cycle_id=cycle_id,
                recipient_membership_id=scenario["a"],
                ownership_version=1,
                reminder_type=ReminderType.cycle_due,
                scheduled_for=dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC),
                state=ReminderState.scheduled,
                dedupe_key="orig-key",
            )
        )
        s.commit()

    with Session(engine) as s:
        contract = handoff.propose_handoff(
            s,
            actor_membership_id=scenario["a"],
            responsibility_id=scenario["resp"],
            target_membership_id=scenario["b"],
        )
        cid = contract.id
        s.commit()
    with Session(engine) as s:
        result = handoff.accept_handoff(
            s, actor_membership_id=scenario["b"], contract_id=cid, idempotency_key="idem-2"
        )
        s.commit()
        assert result.reminders_rerouted == 1

    with Session(engine) as s:
        # Old reminder superseded; new one is scheduled, owned by B, at version 2.
        old = s.execute(select(Reminder).where(Reminder.dedupe_key == "orig-key")).scalar_one()
        assert old.state is ReminderState.superseded

        live = (
            s.execute(select(Reminder).where(Reminder.state == ReminderState.scheduled))
            .scalars()
            .all()
        )
        assert len(live) == 1
        assert live[0].recipient_membership_id == scenario["b"]
        assert live[0].ownership_version == 2


def test_accept_is_idempotent_on_replay(engine: Engine, scenario) -> None:
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=scenario["a"],
            responsibility_id=scenario["resp"],
            target_membership_id=scenario["b"],
        ).id
        s.commit()

    with Session(engine) as s:
        r1 = handoff.accept_handoff(
            s, actor_membership_id=scenario["b"], contract_id=cid, idempotency_key="dup"
        )
        s.commit()
    with Session(engine) as s:
        r2 = handoff.accept_handoff(
            s, actor_membership_id=scenario["b"], contract_id=cid, idempotency_key="dup"
        )
        s.commit()

    assert r1.ownership_version == r2.ownership_version == 2
    assert r2.replayed is True

    with Session(engine) as s:
        transferred = s.execute(
            select(func.count())
            .select_from(OwnershipEvent)
            .where(OwnershipEvent.event_type == OwnershipEventType.transferred)
        ).scalar_one()
        assert transferred == 1  # exactly one effect


def test_only_proposed_owner_can_accept(engine: Engine, scenario) -> None:
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=scenario["a"],
            responsibility_id=scenario["resp"],
            target_membership_id=scenario["b"],
        ).id
        s.commit()
    with Session(engine) as s, pytest.raises(NotAuthorized):
        handoff.accept_handoff(
            s, actor_membership_id=scenario["a"], contract_id=cid, idempotency_key="x"
        )


def test_scope_edit_makes_contract_stale(engine: Engine, scenario) -> None:
    with Session(engine) as s:
        cid = handoff.propose_handoff(
            s,
            actor_membership_id=scenario["a"],
            responsibility_id=scenario["resp"],
            target_membership_id=scenario["b"],
        ).id
        s.commit()
    # Simulate a scope edit bumping scope_version.
    with Session(engine) as s:
        resp = s.get(Responsibility, scenario["resp"])
        resp.scope_version += 1
        s.commit()
    with Session(engine) as s, pytest.raises(StaleContract):
        handoff.accept_handoff(
            s, actor_membership_id=scenario["b"], contract_id=cid, idempotency_key="y"
        )


def _make_cycle(session: Session, resp: Responsibility) -> uuid.UUID:
    from relay.core.models import ResponsibilityCycle

    c = ResponsibilityCycle(responsibility_id=resp.id, sequence=1)
    session.add(c)
    session.flush()
    return c.id
