"""The database — not just Python — must prevent invalid domain state."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relay.core.enums import ReminderState, ReminderType, ResponsibilityStatus
from relay.core.models import Reminder, StepDependency
from tests.factories import (
    make_cycle,
    make_household,
    make_membership,
    make_responsibility,
    make_step,
    make_user,
)

pytestmark = pytest.mark.integration


def test_email_uniqueness_enforced(engine: Engine) -> None:
    with Session(engine) as s:
        make_user(s, email="dup@example.com")
        s.commit()
    with Session(engine) as s, pytest.raises(IntegrityError):
        make_user(s, email="dup@example.com")
        s.commit()


def test_membership_unique_per_household(engine: Engine) -> None:
    from relay.core.models import Membership

    with Session(engine) as s:
        u = make_user(s)
        h = make_household(s)
        make_membership(s, u, h)
        s.commit()
        user_id, household_id = u.id, h.id
    with Session(engine) as s, pytest.raises(IntegrityError):
        s.add(Membership(user_id=user_id, household_id=household_id))
        s.commit()


def test_non_draft_responsibility_requires_owner(engine: Engine) -> None:
    with Session(engine) as s:
        u = make_user(s)
        h = make_household(s)
        m = make_membership(s, u, h)
        # Draft without owner is fine.
        make_responsibility(s, h, m, status=ResponsibilityStatus.draft)
        s.commit()
    with Session(engine) as s, pytest.raises(IntegrityError):
        u = make_user(s)
        h = make_household(s)
        m = make_membership(s, u, h)
        # Active without an owner violates the check constraint.
        make_responsibility(s, h, m, owner=None, status=ResponsibilityStatus.active)
        s.commit()


def test_cycle_sequence_unique_per_responsibility(engine: Engine) -> None:
    with Session(engine) as s:
        u = make_user(s)
        h = make_household(s)
        m = make_membership(s, u, h)
        r = make_responsibility(s, h, m)
        make_cycle(s, r, sequence=1)
        s.commit()
        with pytest.raises(IntegrityError):
            make_cycle(s, r, sequence=1)
            s.commit()


def test_self_step_dependency_rejected(engine: Engine) -> None:
    with Session(engine) as s:
        u = make_user(s)
        h = make_household(s)
        m = make_membership(s, u, h)
        r = make_responsibility(s, h, m)
        c = make_cycle(s, r)
        step = make_step(s, c)
        s.commit()
        with pytest.raises(IntegrityError):
            s.add(StepDependency(cycle_id=c.id, from_step_id=step.id, to_step_id=step.id))
            s.commit()


def test_reminder_dedupe_key_unique(engine: Engine) -> None:
    with Session(engine) as s:
        u = make_user(s)
        h = make_household(s)
        m = make_membership(s, u, h)
        r = make_responsibility(s, h, m, owner=m, status=ResponsibilityStatus.active)
        c = make_cycle(s, r)
        s.flush()

        def _reminder() -> Reminder:
            return Reminder(
                responsibility_id=r.id,
                cycle_id=c.id,
                recipient_membership_id=m.id,
                ownership_version=1,
                reminder_type=ReminderType.cycle_due,
                scheduled_for=__import__("datetime").datetime.now(__import__("datetime").UTC),
                state=ReminderState.scheduled,
                dedupe_key="same-key",
            )

        s.add(_reminder())
        s.commit()
        with pytest.raises(IntegrityError):
            s.add(_reminder())
            s.commit()


def test_missing_responsibility_fk_rejected(engine: Engine) -> None:
    with Session(engine) as s, pytest.raises(IntegrityError):
        make_cycle(s, _FakeResp(uuid.uuid4()))  # type: ignore[arg-type]
        s.commit()


class _FakeResp:
    def __init__(self, id: uuid.UUID) -> None:
        self.id = id
