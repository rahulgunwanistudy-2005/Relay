from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, EmailStr, Field

from relay.core.enums import MembershipRole


class HouseholdCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    timezone: str = Field(default="UTC", max_length=64)


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    household_id: uuid.UUID
    role: MembershipRole
    is_active: bool
    # Human identity so the client never has to render a raw UUID for a person.
    display_name: str
    email: str

    model_config = {"from_attributes": True}


class InviteCreateRequest(BaseModel):
    email: EmailStr | None = None
    role: MembershipRole = MembershipRole.member


class InviteResponse(BaseModel):
    invite_id: uuid.UUID
    token: str
    household_id: uuid.UUID
    expires_at: dt.datetime


class InviteAcceptResponse(BaseModel):
    membership_id: uuid.UUID
    household_id: uuid.UUID
    role: MembershipRole
