"""Record delivery evidence for every channel attempt."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.orm import Session

from relay.core.enums import DeliveryStatus
from relay.notifications.channels import NotificationChannel, NotificationMessage
from relay.notifications.models import NotificationDelivery

_SUCCESS = {DeliveryStatus.delivered, DeliveryStatus.provider_accepted}


def deliver(
    session: Session,
    *,
    channel: NotificationChannel,
    recipient_membership_id: uuid.UUID,
    message: NotificationMessage,
    now: dt.datetime,
    attempt: int = 1,
) -> NotificationDelivery:
    """Attempt delivery on one channel and persist a NotificationDelivery row.
    The row is written whether the attempt succeeds or fails."""
    result = channel.send(
        session=session, recipient_membership_id=recipient_membership_id, message=message
    )
    record = NotificationDelivery(
        reminder_id=message.reminder_id,
        channel=channel.channel,
        recipient_membership_id=recipient_membership_id,
        provider_message_id=result.provider_message_id,
        attempt=attempt,
        status=result.status,
        delivered_at=now if result.status in _SUCCESS else None,
        failure_type=result.failure_type,
        provider_response=result.provider_response,
    )
    session.add(record)
    session.flush()
    return record
