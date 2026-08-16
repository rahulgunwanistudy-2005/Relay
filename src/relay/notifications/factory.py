"""Build the active notification channels from configuration."""

from __future__ import annotations

from relay.config import Settings
from relay.notifications.channels import InAppChannel, NotificationChannel, SmtpChannel


def build_channels(settings: Settings) -> list[NotificationChannel]:
    """In-app is always on. SMTP is added when explicitly enabled."""
    channels: list[NotificationChannel] = [InAppChannel()]
    if settings.smtp_enabled:
        channels.append(
            SmtpChannel(
                host=settings.smtp_host,
                port=settings.smtp_port,
                sender=settings.smtp_from,
                username=settings.smtp_username,
                password=settings.smtp_password,
            )
        )
    return channels
