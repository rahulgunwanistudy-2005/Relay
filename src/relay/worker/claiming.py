"""Durable claiming with ``FOR UPDATE SKIP LOCKED``.

Multiple workers can run concurrently: each claims a disjoint batch. Outbox rows
carry a lease so a crashed worker's in-flight rows become reclaimable once the
lease expires (restart recovery).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from relay.core.enums import OutboxStatus, ReminderState
from relay.core.models import Reminder
from relay.core.models.outbox import OutboxEvent


def claim_due_reminders(session: Session, *, now: dt.datetime, limit: int) -> list[Reminder]:
    """Lock a batch of scheduled reminders that are due. The state transition to
    ``fired`` (by the caller) makes reprocessing a no-op."""
    return list(
        session.execute(
            select(Reminder)
            .where(
                Reminder.state == ReminderState.scheduled,
                Reminder.scheduled_for <= now,
            )
            .order_by(Reminder.scheduled_for)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )


def claim_outbox(
    session: Session,
    *,
    now: dt.datetime,
    worker_id: str,
    lease_seconds: int,
    limit: int,
) -> list[OutboxEvent]:
    """Claim pending outbox rows (and reclaim any whose lease has expired)."""
    rows = list(
        session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.available_at <= now,
                or_(
                    OutboxEvent.status == OutboxStatus.pending,
                    (OutboxEvent.status == OutboxStatus.processing)
                    & (OutboxEvent.lease_expires_at < now),
                ),
            )
            .order_by(OutboxEvent.available_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        .scalars()
        .all()
    )
    lease_until = now + dt.timedelta(seconds=lease_seconds)
    for row in rows:
        row.status = OutboxStatus.processing
        row.lease_owner = worker_id
        row.lease_expires_at = lease_until
    return rows
