"""Security middleware: headers, body-size cap, and a simple rate limiter.

The rate limiter is a per-process fixed-window counter — adequate for a single
node and the demo; a multi-node deployment would move this to Redis. Documented
as such rather than pretending to be distributed.
"""

from __future__ import annotations

import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > self._max:
                    return JSONResponse(status_code=413, content={"error": "payload_too_large"})
            except ValueError:
                return JSONResponse(status_code=400, content={"error": "bad_content_length"})
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, per_minute: int) -> None:
        super().__init__(app)
        self._limit = per_minute
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[int, int]] = {}

    def _client(self, request: Request) -> str:
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/health"):
            return await call_next(request)
        window = int(time.time() // 60)
        key = self._client(request)
        with self._lock:
            start, count = self._buckets.get(key, (window, 0))
            if start != window:
                start, count = window, 0
            count += 1
            self._buckets[key] = (start, count)
            over = count > self._limit
        if over:
            return JSONResponse(status_code=429, content={"error": "rate_limited"})
        return await call_next(request)
