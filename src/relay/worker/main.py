"""Worker entrypoint: ``python -m relay.worker.main``."""

from __future__ import annotations

import os
import signal
import socket

from relay.config import get_settings
from relay.core.clock import SystemClock
from relay.db.session import get_engine
from relay.logging import configure_logging, get_logger

log = get_logger("relay.worker")


def build_worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    # Imported for side effect: register operational tables on Base.metadata.
    from relay.worker.runner import Worker

    engine = get_engine()
    worker = Worker(
        engine,
        build_worker_id(),
        clock=SystemClock(),
        poll_interval_s=settings.worker_poll_interval_s,
    )

    def _handle_signal(signum, _frame):
        log.info("worker.signal", signum=signum)
        worker.request_stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    worker.run()


if __name__ == "__main__":
    main()
