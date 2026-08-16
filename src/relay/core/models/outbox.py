"""Transactional outbox — durable post-commit work with lease-based claiming."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import OutboxStatus
from relay.core.models._helpers import pg_enum
from relay.db.base import Base


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        # Claim scan: pending + available now, ordered by availability.
        Index("ix_outbox_claimable", "status", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[OutboxStatus] = mapped_column(
        pg_enum(OutboxStatus, "outbox_status"),
        nullable=False,
        default=OutboxStatus.pending,
    )
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
    available_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
    processed_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
