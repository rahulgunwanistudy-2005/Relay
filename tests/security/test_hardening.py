"""Security hardening: headers, body-size cap, rate limiting, safe 500s."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from relay.api.errors import install_error_handlers
from relay.api.security_mw import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)

pytestmark = pytest.mark.security


def test_security_headers_present(client) -> None:
    resp = client.get("/health/live")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


def _mini_app(*middlewares) -> FastAPI:
    app = FastAPI()
    for mw, kwargs in middlewares:
        app.add_middleware(mw, **kwargs)
    install_error_handlers(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.post("/echo")
    def echo(payload: dict):
        return payload

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail: db password leak")

    return app


def test_oversized_body_rejected() -> None:
    app = _mini_app((BodySizeLimitMiddleware, {"max_bytes": 50}))
    client = TestClient(app)
    resp = client.post("/echo", json={"data": "x" * 500})
    assert resp.status_code == 413
    assert resp.json()["error"] == "payload_too_large"


def test_rate_limit_triggers() -> None:
    app = _mini_app((RateLimitMiddleware, {"per_minute": 2}))
    client = TestClient(app)
    assert client.get("/ok").status_code == 200
    assert client.get("/ok").status_code == 200
    third = client.get("/ok")
    assert third.status_code == 429
    assert third.json()["error"] == "rate_limited"


def test_unhandled_error_returns_generic_500_without_traceback() -> None:
    app = _mini_app((SecurityHeadersMiddleware, {}))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.text
    assert resp.json() == {"error": "internal_error"}
    # No internal details leak to the client.
    assert "secret internal detail" not in body
    assert "Traceback" not in body
