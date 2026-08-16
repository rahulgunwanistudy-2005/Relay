"""Household and membership routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from relay.api.deps import get_current_user, get_db, require_membership
from relay.api.schemas.household import (
    HouseholdCreateRequest,
    HouseholdResponse,
    InviteAcceptResponse,
    InviteCreateRequest,
    InviteResponse,
    MemberResponse,
)
from relay.core.application import households
from relay.core.models import Household, Membership, User

router = APIRouter(prefix="/v1", tags=["households"])


@router.post("/households", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(
    body: HouseholdCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Household:
    household, _membership = households.create_household(
        db, user=user, name=body.name, timezone=body.timezone
    )
    return household


@router.get("/households/{household_id}", response_model=HouseholdResponse)
def get_household(
    household_id: uuid.UUID,
    membership: Membership = Depends(require_membership),
    db: Session = Depends(get_db),
) -> Household:
    # Authorization enforced by require_membership; scope the fetch to it. The
    # membership's FK guarantees the household row exists.
    household = db.get(Household, membership.household_id)
    assert household is not None
    return household


@router.get("/households/{household_id}/members", response_model=list[MemberResponse])
def list_members(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Membership]:
    return households.list_members(db, user_id=user.id, household_id=household_id)


@router.post(
    "/households/{household_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    household_id: uuid.UUID,
    body: InviteCreateRequest,
    membership: Membership = Depends(require_membership),
    db: Session = Depends(get_db),
) -> InviteResponse:
    invite, token = households.create_invite(db, actor=membership, email=body.email, role=body.role)
    return InviteResponse(
        invite_id=invite.id,
        token=token,
        household_id=invite.household_id,
        expires_at=invite.expires_at,
    )


@router.post("/invites/{token}/accept", response_model=InviteAcceptResponse)
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InviteAcceptResponse:
    membership = households.accept_invite(db, user=user, token=token)
    return InviteAcceptResponse(
        membership_id=membership.id,
        household_id=membership.household_id,
        role=membership.role,
    )
