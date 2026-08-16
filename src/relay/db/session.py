"""Engine and session lifecycle.

Sync SQLAlchemy + psycopg3. Route handlers are plain ``def`` so they run in the
threadpool and use these sync sessions directly; the worker uses the same
machinery for ``FOR UPDATE SKIP LOCKED`` job claiming.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from relay.config import get_settings


def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.sync_database_url,
        pool_pre_ping=True,
        future=True,
    )


engine: Engine = get_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, future=True
)


def sessionmaker_for(bound_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=bound_engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error, always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
