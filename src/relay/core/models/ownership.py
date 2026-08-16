"""Ownership contracts and the append-only ownership event log."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import ContractStatus, OwnershipEventType
from relay.core.models._helpers import pg_enum
from relay.db.base import Base, TimestampMixin


class OwnershipContract(Base, TimestampMixin):
    """A proposed transfer. Remains inspectable after later scope changes because
    it snapshots the scope/completion/recurrence it was agreed against."""

    __tablename__ = "ownership_contracts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    responsibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proposer_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False
    )
    # Null for an initial claim of an unowned draft.
    source_owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=True
    )
    proposed_owner_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    expected_scope_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_ownership_version: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[ContractStatus] = mapped_column(
        pg_enum(ContractStatus, "contract_status"),
        nullable=False,
        default=ContractStatus.pending,
        index=True,
    )

    completion_standard_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle_scope_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    recurrence_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    # Explicit escalation/backup routing. Empty means no implicit fallback.
    backup_policy: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    proposed_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    declined_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)


class OwnershipEvent(Base):
    """Append-only. Rows are never edited; ownership history reconstructs from here."""

    __tablename__ = "ownership_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    responsibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ownership_contracts.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[OwnershipEventType] = mapped_column(
        pg_enum(OwnershipEventType, "ownership_event_type"), nullable=False
    )
    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    previous_owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    new_owner_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    ownership_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        server_default=func.now(), nullable=False, index=True
    )
