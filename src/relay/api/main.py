"""FastAPI application factory — thin. Wiring only; logic lives in services."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from relay.api.errors import install_error_handlers
from relay.api.health import router as health_router
from relay.api.middleware import RequestIdMiddleware
from relay.api.routers.auth import router as auth_router
from relay.api.routers.handoffs import router as handoffs_router
from relay.api.routers.households import router as households_router
from relay.api.routers.queue import router as queue_router
from relay.api.routers.responsibilities import router as responsibilities_router
from relay.api.security_mw import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from relay.config import get_settings
from relay.logging import configure_logging, get_logger

log = get_logger("relay.api")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)

    app = FastAPI(
        title="Relay API",
        version="0.0.0",
        description="Responsibility-transfer engine",
    )
    # Middleware (last added is outermost). Request-id outermost for logging.
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(households_router)
    app.include_router(responsibilities_router)
    app.include_router(handoffs_router)
    app.include_router(queue_router)

    log.info("api.startup", environment=settings.environment.value)
    return app


app = create_app()
