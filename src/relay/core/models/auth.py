"""Authentication persistence: opaque server-side sessions and household invites.

Session tokens are random; only their hash is stored, so a DB leak does not
yield usable tokens. Logout revokes; expiry and revocation are checked on every
authenticated request.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import MembershipRole
from relay.core.models._helpers import pg_enum
from relay.db.base import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Optional targeting; when set, only this email may accept.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[MembershipRole] = mapped_column(
        pg_enum(MembershipRole, "membership_role"),
        nullable=False,
        default=MembershipRole.member,
    )
    expires_at: Mapped[dt.datetime] = mapped_column(nullable=False)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    accepted_by_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
