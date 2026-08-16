"""Identity & tenancy: User, Household, Membership.

Authorization is always scoped through Membership — never User directly.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from relay.core.enums import AccountState, MembershipRole
from relay.core.models._helpers import pg_enum
from relay.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Stored normalized (lowercased, trimmed). Uniqueness enforced in DB.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_state: Mapped[AccountState] = mapped_column(
        pg_enum(AccountState, "account_state"),
        nullable=False,
        default=AccountState.active,
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Household(Base, TimestampMixin):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # IANA timezone, e.g. "America/New_York". Recurrence math depends on it.
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="household", cascade="all, delete-orphan"
    )


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "household_id", name="uq_memberships_user_household"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        pg_enum(MembershipRole, "membership_role"),
        nullable=False,
        default=MembershipRole.member,
    )
    notification_prefs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="memberships")
    household: Mapped[Household] = relationship(back_populates="memberships")
