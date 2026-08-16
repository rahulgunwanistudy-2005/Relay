"""Worker run loop.

A durable, restart-safe loop driven by an injectable Clock. Each tick records a
heartbeat, fires due reminders, and drains the outbox — all via
``FOR UPDATE SKIP LOCKED`` claiming with leases and retries, so multiple workers
are safe and a crash leaves no obligation behind.
"""

from __future__ import annotations

import threading

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from relay.config import Settings, get_settings
from relay.core.clock import Clock, SystemClock
from relay.logging import get_logger
from relay.notifications.channels import NotificationChannel
from relay.notifications.factory import build_channels
from relay.worker.heartbeat import record_heartbeat
from relay.worker.processing import (
    DEFAULT_HANDLERS,
    OutboxHandler,
    fire_due_reminders,
    process_outbox,
)

log = get_logger("relay.worker")


class Worker:
    def __init__(
        self,
        engine: Engine,
        worker_id: str,
        *,
        clock: Clock | None = None,
        poll_interval_s: float = 1.0,
        settings: Settings | None = None,
        channels: list[NotificationChannel] | None = None,
        handlers: dict[str, OutboxHandler] | None = None,
    ) -> None:
        self._engine = engine
        self._worker_id = worker_id
        self._clock = clock or SystemClock()
        self._poll_interval_s = poll_interval_s
        self._settings = settings or get_settings()
        self._channels = channels if channels is not None else build_channels(self._settings)
        self._handlers = handlers if handlers is not None else DEFAULT_HANDLERS
        self._stop = threading.Event()
        self._ticks = 0

    def request_stop(self) -> None:
        self._stop.set()

    def tick(self) -> int:
        """Run exactly one iteration. Returns units of work processed.

        Separated from the loop so tests can drive iterations deterministically
        with a FrozenClock and no real sleeping.
        """
        now = self._clock.now()
        with Session(self._engine) as session:
            record_heartbeat(session, self._worker_id, now)
            processed = self._process_due_work(session, now)
            session.commit()
        self._ticks += 1
        return processed

    def _process_due_work(self, session: Session, now) -> int:
        s = self._settings
        fired = fire_due_reminders(
            session,
            channels=self._channels,
            now=now,
            deep_link_base=s.deep_link_base,
            limit=s.worker_batch_size,
        )
        drained = process_outbox(
            session,
            now=now,
            worker_id=self._worker_id,
            lease_seconds=s.worker_lease_seconds,
            max_attempts=s.worker_max_attempts,
            backoff_s=s.worker_retry_backoff_s,
            limit=s.worker_batch_size,
            handlers=self._handlers,
        )
        return fired + drained

    def run(self) -> None:
        start = self._clock.now()
        log.info("worker.start", worker_id=self._worker_id, started_at=start.isoformat())
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:  # keep the loop alive; surface the failure
                log.exception("worker.tick_failed", worker_id=self._worker_id)
            # Interruptible wait so shutdown is prompt.
            self._stop.wait(self._poll_interval_s)
        log.info("worker.stop", worker_id=self._worker_id, ticks=self._ticks)
