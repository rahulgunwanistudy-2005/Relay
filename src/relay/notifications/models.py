"""Persistence for notification delivery evidence. Lives in relay.notifications."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import DeliveryChannel, DeliveryStatus
from relay.core.models._helpers import pg_enum
from relay.db.base import Base


class NotificationDelivery(Base):
    """One row per provider attempt. "delivered" is only set on provider confirmation."""

    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[DeliveryChannel] = mapped_column(
        pg_enum(DeliveryChannel, "delivery_channel"), nullable=False
    )
    recipient_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[DeliveryStatus] = mapped_column(
        pg_enum(DeliveryStatus, "delivery_status"),
        nullable=False,
        default=DeliveryStatus.queued,
    )
    requested_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
    delivered_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    failure_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Sanitized provider response only — never raw sensitive content.
    provider_response: Mapped[str | None] = mapped_column(Text, nullable=True)


class InAppNotification(Base):
    """The persisted in-app inbox entry a recipient sees in the app."""

    __tablename__ = "in_app_notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    responsibility_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("responsibilities.id", ondelete="CASCADE"), nullable=True
    )
    reminder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reminders.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
