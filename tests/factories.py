"""Minimal builders for domain rows in tests.

These insert via the ORM/session directly (appropriate for exercising DB
constraints). Service-level flows are exercised in their own tests.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from relay.core.enums import LifecycleKind, ResponsibilityStatus
from relay.core.models import (
    Household,
    LifecycleStep,
    Membership,
    Responsibility,
    ResponsibilityCycle,
    User,
)


def make_user(session: Session, email: str | None = None, name: str = "Test User") -> User:
    user = User(
        email=email or f"user-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        display_name=name,
    )
    session.add(user)
    session.flush()
    return user


def make_household(session: Session, name: str = "Home", tz: str = "UTC") -> Household:
    hh = Household(name=name, timezone=tz)
    session.add(hh)
    session.flush()
    return hh


def make_membership(session: Session, user: User, household: Household) -> Membership:
    m = Membership(user_id=user.id, household_id=household.id)
    session.add(m)
    session.flush()
    return m


def make_responsibility(
    session: Session,
    household: Household,
    creator: Membership,
    *,
    owner: Membership | None = None,
    status: ResponsibilityStatus = ResponsibilityStatus.draft,
    title: str = "A responsibility",
) -> Responsibility:
    r = Responsibility(
        household_id=household.id,
        title=title,
        created_by_membership_id=creator.id,
        current_owner_membership_id=owner.id if owner else None,
        status=status,
    )
    session.add(r)
    session.flush()
    return r


def make_cycle(
    session: Session, responsibility: Responsibility, sequence: int = 1
) -> ResponsibilityCycle:
    c = ResponsibilityCycle(responsibility_id=responsibility.id, sequence=sequence)
    session.add(c)
    session.flush()
    return c


def make_step(
    session: Session,
    cycle: ResponsibilityCycle,
    step_key: str = "execute",
    kind: LifecycleKind = LifecycleKind.execute,
) -> LifecycleStep:
    s = LifecycleStep(
        cycle_id=cycle.id,
        step_key=step_key,
        kind=kind,
        description="do the thing",
    )
    session.add(s)
    session.flush()
    return s
