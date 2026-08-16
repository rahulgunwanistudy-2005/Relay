"""Notification delivery: in-app and a REAL external SMTP send.

The SMTP test runs a genuine in-process SMTP server (aiosmtpd) and asserts the
message was accepted and received — no manual DB edits, no mocked transport.
"""

from __future__ import annotations

import datetime as dt

import pytest
from aiosmtpd.controller import Controller
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from relay.core.enums import DeliveryStatus, ResponsibilityStatus
from relay.notifications.channels import InAppChannel, NotificationMessage, SmtpChannel
from relay.notifications.delivery import deliver
from relay.notifications.models import InAppNotification, NotificationDelivery
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.worker]

NOW = dt.datetime(2026, 6, 1, tzinfo=dt.UTC)


class _CollectingHandler:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.recipients: list[str] = []

    async def handle_DATA(self, server, session, envelope):  # noqa: N802 (aiosmtpd API)
        self.recipients.extend(envelope.rcpt_tos)
        self.messages.append(envelope.content.decode("utf-8", errors="replace"))
        return "250 OK"


@pytest.fixture
def recipient(engine: Engine):
    with Session(engine) as s:
        hh = make_household(s)
        m = make_membership(s, make_user(s, email="recv@example.com"), hh)
        resp = make_responsibility(s, hh, m, owner=m, status=ResponsibilityStatus.active)
        s.commit()
        return {"membership": m.id, "resp": resp.id}


def test_in_app_delivery_persists_notification_and_evidence(engine: Engine, recipient) -> None:
    with Session(engine) as s:
        record = deliver(
            s,
            channel=InAppChannel(),
            recipient_membership_id=recipient["membership"],
            message=NotificationMessage(
                subject="Hi", body="body", responsibility_id=recipient["resp"]
            ),
            now=NOW,
        )
        s.commit()
        assert record.status is DeliveryStatus.delivered
        assert record.delivered_at is not None

    with Session(engine) as s:
        assert s.execute(select(InAppNotification)).scalar_one().title == "Hi"


def _free_port() -> int:
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_real_smtp_send_is_accepted_and_recorded(engine: Engine, recipient) -> None:
    handler = _CollectingHandler()
    port = _free_port()
    controller = Controller(handler, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        channel = SmtpChannel(host="127.0.0.1", port=port, sender="relay@example.com")
        with Session(engine) as s:
            record = deliver(
                s,
                channel=channel,
                recipient_membership_id=recipient["membership"],
                message=NotificationMessage(
                    subject="Due soon", body="Open Relay", deep_link="http://x/y"
                ),
                now=NOW,
            )
            s.commit()
            assert record.status is DeliveryStatus.provider_accepted
            assert record.provider_message_id
            assert record.delivered_at is not None
    finally:
        controller.stop()

    # The SMTP server actually received the message for the real recipient.
    assert handler.recipients == ["recv@example.com"]
    assert "Due soon" in handler.messages[0]

    with Session(engine) as s:
        d = s.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.status == DeliveryStatus.provider_accepted
            )
        ).scalar_one()
        assert d.channel.value == "email"


def test_smtp_transport_failure_is_retryable(engine: Engine, recipient) -> None:
    # Point at a closed port: transport error -> retryable_failure, evidence recorded.
    channel = SmtpChannel(host="127.0.0.1", port=1, sender="relay@example.com")
    with Session(engine) as s:
        record = deliver(
            s,
            channel=channel,
            recipient_membership_id=recipient["membership"],
            message=NotificationMessage(subject="x", body="y"),
            now=NOW,
        )
        s.commit()
        assert record.status is DeliveryStatus.retryable_failure
        assert record.delivered_at is None
        assert record.failure_type
