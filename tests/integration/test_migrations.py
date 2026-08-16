"""Prove migrations build the schema from an empty database and fully reverse.

Runs against a dedicated throwaway database so it never collides with the
create_all-built schema the rest of the suite uses.
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, make_url, text

from relay.config import get_settings

pytestmark = pytest.mark.integration

MIGRATION_DB = "relay_migration_test"


@pytest.fixture
def fresh_db_url() -> str:
    base = make_url(get_settings().sync_database_url)
    admin = base.set(database="postgres")
    admin_engine = create_engine(str(admin), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{MIGRATION_DB}"'))
    admin_engine.dispose()

    yield str(base.set(database=MIGRATION_DB))

    admin_engine = create_engine(str(admin), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{MIGRATION_DB}" WITH (FORCE)'))
    admin_engine.dispose()


def _alembic_config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_then_downgrade_base(fresh_db_url: str) -> None:
    cfg = _alembic_config(fresh_db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(fresh_db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.worker_heartbeat')")).scalar()
    engine.dispose()

    command.downgrade(cfg, "base")
    engine = create_engine(fresh_db_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.worker_heartbeat')")).scalar() is None
    engine.dispose()
