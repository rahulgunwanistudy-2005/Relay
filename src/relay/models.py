"""Model registry.

Importing this module imports every module that defines ORM tables, so
``Base.metadata`` is complete for Alembic autogenerate and for tests that call
``create_all``. Add new model modules here as phases land.
"""

from __future__ import annotations

from relay.ai import models as _ai_models  # noqa: F401
from relay.core import models as _core_models  # noqa: F401
from relay.db.base import Base
from relay.notifications import models as _notification_models  # noqa: F401
from relay.worker import models as _worker_models  # noqa: F401

__all__ = ["Base"]
