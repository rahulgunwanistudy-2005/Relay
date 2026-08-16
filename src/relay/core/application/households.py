"""Household services: creation, membership authorization, invites."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay.core.application.errors import Conflict, InvalidState, NotAuthorized, NotFound
from relay.core.clock import Clock, SystemClock
from relay.core.enums import MembershipRole
from relay.core.models import Household, HouseholdInvite, Membership, User
from relay.core.security import generate_token, hash_token, normalize_email

DEFAULT_INVITE_TTL = dt.timedelta(days=7)
_ADMIN_ROLES = frozenset({MembershipRole.owner, MembershipRole.admin})


def create_household(
    session: Session, *, user: User, name: str, timezone: str = "UTC"
) -> tuple[Household, Membership]:
    household = Household(name=name.strip(), timezone=timezone)
    session.add(household)
    session.flush()
    membership = Membership(user_id=user.id, household_id=household.id, role=MembershipRole.owner)
    session.add(membership)
    session.flush()
    return household, membership


def list_households_for_user(session: Session, *, user_id: uuid.UUID) -> list[Household]:
    """Households the user is an active member of.

    Read-only navigation aid so a returning client does not depend on
    client-side storage to rediscover its own tenancy. Authorization is still
    enforced per resource by ``require_membership`` on every other route.
    """
    return list(
        session.execute(
            select(Household)
            .join(Membership, Membership.household_id == Household.id)
            .where(Membership.user_id == user_id, Membership.is_active.is_(True))
            .order_by(Household.created_at)
        ).scalars()
    )


def require_membership(
    session: Session, *, user_id: uuid.UUID, household_id: uuid.UUID
) -> Membership:
    """Server-side authorization: the user must be an active member. This is the
    only sanctioned way to authorize a household-scoped resource."""
    membership = session.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.household_id == household_id,
            Membership.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if membership is None:
        # Fail closed: do not distinguish "not a member" from "no such household".
        raise NotFound("household not found")
    return membership


def list_members(
    session: Session, *, user_id: uuid.UUID, household_id: uuid.UUID
) -> list[Membership]:
    require_membership(session, user_id=user_id, household_id=household_id)
    return list(
        session.execute(select(Membership).where(Membership.household_id == household_id)).scalars()
    )


def create_invite(
    session: Session,
    *,
    actor: Membership,
    email: str | None = None,
    role: MembershipRole = MembershipRole.member,
    clock: Clock = SystemClock(),
    ttl: dt.timedelta = DEFAULT_INVITE_TTL,
) -> tuple[HouseholdInvite, str]:
    if actor.role not in _ADMIN_ROLES:
        raise NotAuthorized("only owners or admins may invite")
    token = generate_token()
    invite = HouseholdInvite(
        household_id=actor.household_id,
        created_by_membership_id=actor.id,
        token_hash=hash_token(token),
        email=normalize_email(email) if email else None,
        role=role,
        expires_at=clock.now() + ttl,
    )
    session.add(invite)
    session.flush()
    return invite, token


def accept_invite(
    session: Session, *, user: User, token: str, clock: Clock = SystemClock()
) -> Membership:
    now = clock.now()
    invite = session.execute(
        select(HouseholdInvite)
        .where(HouseholdInvite.token_hash == hash_token(token))
        .with_for_update()
    ).scalar_one_or_none()
    if invite is None:
        raise NotFound("invite not found")
    if invite.revoked_at is not None:
        raise InvalidState("invite revoked")
    if invite.accepted_at is not None:
        raise InvalidState("invite already used")
    if invite.expires_at <= now:
        raise InvalidState("invite expired")
    if invite.email is not None and invite.email != user.email:
        raise NotAuthorized("invite was issued to a different email")

    existing = session.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.household_id == invite.household_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.is_active:
            raise Conflict("already a member of this household")
        existing.is_active = True
        existing.revoked_at = None
        membership = existing
    else:
        membership = Membership(user_id=user.id, household_id=invite.household_id, role=invite.role)
        session.add(membership)
        session.flush()

    invite.accepted_at = now
    invite.accepted_by_membership_id = membership.id
    return membership
