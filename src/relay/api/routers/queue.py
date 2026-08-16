"""The caller's load: ghost queue (scheduled reminders) and notifications."""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from relay.api.deps import get_current_user, get_db
from relay.api.schemas.responsibility import GhostQueueItem, IncomingHandoff, NotificationOut
from relay.core.application.errors import NotFound
from relay.core.enums import ContractStatus, ReminderState
from relay.core.models import (
    Membership,
    OwnershipContract,
    Reminder,
    Responsibility,
    User,
)
from relay.notifications.models import InAppNotification

router = APIRouter(prefix="/v1", tags=["queue"])


def _my_membership_ids(db: Session, user: User) -> list[uuid.UUID]:
    return list(
        db.execute(
            select(Membership.id).where(
                Membership.user_id == user.id, Membership.is_active.is_(True)
            )
        ).scalars()
    )


@router.get("/me/ghost-queue", response_model=list[GhostQueueItem])
def ghost_queue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GhostQueueItem]:
    membership_ids = _my_membership_ids(db, user)
    if not membership_ids:
        return []
    rows = (
        db.execute(
            select(Reminder)
            .where(
                Reminder.recipient_membership_id.in_(membership_ids),
                Reminder.state == ReminderState.scheduled,
            )
            .order_by(Reminder.scheduled_for)
        )
        .scalars()
        .all()
    )
    return [
        GhostQueueItem(
            reminder_id=r.id,
            responsibility_id=r.responsibility_id,
            reminder_type=r.reminder_type,
            scheduled_for=r.scheduled_for,
        )
        for r in rows
    ]


@router.get("/me/handoffs", response_model=list[IncomingHandoff])
def incoming_handoffs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IncomingHandoff]:
    """Pending ownership contracts proposed to the caller.

    Read-only. Lets a recipient discover a handoff waiting for them instead of
    relying on an out-of-band contract link. Ownership is unchanged until the
    recipient explicitly accepts.
    """
    membership_ids = _my_membership_ids(db, user)
    if not membership_ids:
        return []
    proposer = aliased(Membership)
    rows = db.execute(
        select(OwnershipContract, Responsibility.title, User.display_name)
        .join(Responsibility, Responsibility.id == OwnershipContract.responsibility_id)
        .join(proposer, proposer.id == OwnershipContract.proposer_membership_id)
        .join(User, User.id == proposer.user_id)
        .where(
            OwnershipContract.proposed_owner_membership_id.in_(membership_ids),
            OwnershipContract.status == ContractStatus.pending,
        )
        .order_by(OwnershipContract.proposed_at.desc())
    ).all()
    return [
        IncomingHandoff(
            contract_id=c.id,
            responsibility_id=c.responsibility_id,
            responsibility_title=title,
            status=c.status.value,
            proposer_display_name=proposer_name,
            proposer_membership_id=c.proposer_membership_id,
            proposed_owner_membership_id=c.proposed_owner_membership_id,
            created_at=c.proposed_at,
        )
        for c, title, proposer_name in rows
    ]


@router.get("/me/notifications", response_model=list[NotificationOut])
def notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InAppNotification]:
    membership_ids = _my_membership_ids(db, user)
    if not membership_ids:
        return []
    return list(
        db.execute(
            select(InAppNotification)
            .where(InAppNotification.recipient_membership_id.in_(membership_ids))
            .order_by(InAppNotification.created_at.desc())
        ).scalars()
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InAppNotification:
    membership_ids = _my_membership_ids(db, user)
    note = db.get(InAppNotification, notification_id)
    if note is None or note.recipient_membership_id not in membership_ids:
        raise NotFound("notification not found")
    if note.read_at is None:
        note.read_at = dt.datetime.now(dt.UTC)
    db.flush()
    return note
