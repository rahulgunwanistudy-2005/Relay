"""Recurrence rule — one per responsibility."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from relay.db.base import Base, TimestampMixin


class RecurrenceRule(Base, TimestampMixin):
    __tablename__ = "recurrence_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    responsibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # iCalendar RRULE string, e.g. "FREQ=MONTHLY;BYMONTHDAY=15".
    rrule: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    anchor_at: Mapped[dt.datetime] = mapped_column(nullable=False)
    next_materialization_at: Mapped[dt.datetime | None] = mapped_column(nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
