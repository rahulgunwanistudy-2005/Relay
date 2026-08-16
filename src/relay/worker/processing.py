"""Processing of claimed work: firing due reminders and draining the outbox.

Effects are idempotent and safe under at-least-once execution: a reminder is
fired exactly once via its state transition; outbox rows retry with backoff and
dead-letter after max attempts.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from relay.core.enums import OutboxStatus, ReminderState
from relay.core.models import Reminder
from relay.core.models.outbox import OutboxEvent
from relay.logging import get_logger
from relay.notifications.channels import NotificationChannel, NotificationMessage
from relay.notifications.delivery import deliver
from relay.worker.claiming import claim_due_reminders, claim_outbox

log = get_logger("relay.worker.processing")

OutboxHandler = Callable[[Session, OutboxEvent], None]


def _reminder_message(reminder: Reminder, deep_link_base: str) -> NotificationMessage:
    # Privacy-minimal: no responsibility content in the notification body, just a
    # deep link the recipient follows to see details in-app.
    link = f"{deep_link_base}/responsibilities/{reminder.responsibility_id}"
    return NotificationMessage(
        subject="A Relay responsibility needs your attention",
        body="One of your responsibilities has an item due. Open Relay to see it.",
        deep_link=link,
        responsibility_id=reminder.responsibility_id,
        reminder_id=reminder.id,
    )


def fire_due_reminders(
    session: Session,
    *,
    channels: list[NotificationChannel],
    now: dt.datetime,
    deep_link_base: str,
    limit: int,
) -> int:
    reminders = claim_due_reminders(session, now=now, limit=limit)
    for reminder in reminders:
        message = _reminder_message(reminder, deep_link_base)
        for channel in channels:
            deliver(
                session,
                channel=channel,
                recipient_membership_id=reminder.recipient_membership_id,
                message=message,
                now=now,
            )
        reminder.state = ReminderState.fired
        reminder.fired_at = now
    if reminders:
        log.info("worker.reminders_fired", count=len(reminders))
    return len(reminders)


def process_outbox(
    session: Session,
    *,
    now: dt.datetime,
    worker_id: str,
    lease_seconds: int,
    max_attempts: int,
    backoff_s: float,
    limit: int,
    handlers: dict[str, OutboxHandler],
) -> int:
    rows = claim_outbox(
        session, now=now, worker_id=worker_id, lease_seconds=lease_seconds, limit=limit
    )
    for row in rows:
        handler = handlers.get(row.event_type)
        try:
            if handler is not None:
                handler(session, row)
            row.status = OutboxStatus.processed
            row.processed_at = now
            row.lease_owner = None
            row.lease_expires_at = None
        except Exception as exc:  # noqa: BLE001 - durable retry boundary
            row.attempt_count += 1
            row.last_error = str(exc)[:1000]
            row.lease_owner = None
            row.lease_expires_at = None
            if row.attempt_count >= max_attempts:
                row.status = OutboxStatus.dead
                log.error("worker.outbox_dead_letter", outbox_id=str(row.id), error=str(exc))
            else:
                row.status = OutboxStatus.pending
                row.available_at = now + dt.timedelta(seconds=backoff_s * row.attempt_count)
    return len(rows)


# --- Default outbox handlers ---


def _handle_handoff_accepted(session: Session, row: OutboxEvent) -> None:
    """Notify the new owner in-app that a responsibility moved to them."""
    from relay.notifications.channels import InAppChannel

    payload = row.payload
    new_owner = payload.get("new_owner_membership_id")
    if not new_owner:
        return
    InAppChannel().send(
        session=session,
        recipient_membership_id=uuid.UUID(new_owner),
        message=NotificationMessage(
            subject="A responsibility was handed to you",
            body="You are now the owner of a responsibility in Relay.",
            responsibility_id=uuid.UUID(payload["responsibility_id"]),
        ),
    )


DEFAULT_HANDLERS: dict[str, OutboxHandler] = {
    "handoff.accepted": _handle_handoff_accepted,
}
