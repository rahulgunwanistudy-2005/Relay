"""Notification channels.

A channel takes a resolved recipient and a message and attempts delivery,
returning a ``DeliveryResult``. "delivered"/"provider_accepted" is only reported
when the effect actually happened (row written / SMTP accepted the message).
"""

from __future__ import annotations

import dataclasses
import smtplib
import uuid
from email.message import EmailMessage
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from relay.core.enums import DeliveryChannel, DeliveryStatus
from relay.core.models import Membership, User
from relay.notifications.models import InAppNotification


@dataclasses.dataclass(frozen=True)
class NotificationMessage:
    subject: str
    body: str
    deep_link: str | None = None
    responsibility_id: uuid.UUID | None = None
    reminder_id: uuid.UUID | None = None


@dataclasses.dataclass(frozen=True)
class DeliveryResult:
    status: DeliveryStatus
    provider_message_id: str | None = None
    failure_type: str | None = None
    provider_response: str | None = None


class NotificationChannel(Protocol):
    channel: DeliveryChannel

    def send(
        self, *, session: Session, recipient_membership_id: uuid.UUID, message: NotificationMessage
    ) -> DeliveryResult: ...


class InAppChannel:
    channel = DeliveryChannel.in_app

    def send(
        self, *, session: Session, recipient_membership_id: uuid.UUID, message: NotificationMessage
    ) -> DeliveryResult:
        note = InAppNotification(
            recipient_membership_id=recipient_membership_id,
            responsibility_id=message.responsibility_id,
            reminder_id=message.reminder_id,
            title=message.subject,
            body=message.body,
            deep_link=message.deep_link,
        )
        session.add(note)
        session.flush()
        return DeliveryResult(status=DeliveryStatus.delivered, provider_message_id=str(note.id))


class SmtpChannel:
    """Real SMTP delivery via stdlib smtplib. In dev, point at Mailpit."""

    channel = DeliveryChannel.email

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._timeout = timeout

    def _recipient_email(self, session: Session, membership_id: uuid.UUID) -> str | None:
        return session.execute(
            select(User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.id == membership_id)
        ).scalar_one_or_none()

    def send(
        self, *, session: Session, recipient_membership_id: uuid.UUID, message: NotificationMessage
    ) -> DeliveryResult:
        to_email = self._recipient_email(session, recipient_membership_id)
        if not to_email:
            return DeliveryResult(
                status=DeliveryStatus.permanent_failure, failure_type="no_recipient_email"
            )

        email = EmailMessage()
        email["Subject"] = message.subject
        email["From"] = self._sender
        email["To"] = to_email
        body = message.body
        if message.deep_link:
            body += f"\n\nOpen in Relay: {message.deep_link}"
        email.set_content(body)
        message_id = email.get("Message-ID") or f"<{uuid.uuid4()}@relay>"
        email["Message-ID"] = message_id

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                if self._username and self._password:
                    smtp.starttls()
                    smtp.login(self._username, self._password)
                smtp.send_message(email)
        except (smtplib.SMTPException, OSError) as exc:
            # Transient transport errors are retryable.
            return DeliveryResult(
                status=DeliveryStatus.retryable_failure,
                failure_type=type(exc).__name__,
                provider_response=str(exc)[:500],
            )
        return DeliveryResult(
            status=DeliveryStatus.provider_accepted, provider_message_id=message_id
        )
