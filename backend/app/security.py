from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings


_SYMBOL_RE = re.compile(r"^[A-Za-z]{4}(\.JK)?$")
_INDEX_RE = re.compile(r"^[A-Za-z0-9]{2,20}$")


def validate_symbol(symbol: str) -> str:
    if not symbol or not _SYMBOL_RE.match(symbol):
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol. Expected a 4-letter IDX ticker, e.g. 'BBCA'.",
        )
    return symbol


def validate_index(index: str | None) -> str | None:
    if index is None:
        return None
    if not _INDEX_RE.match(index):
        raise HTTPException(
            status_code=400,
            detail="Invalid index. Expected an alphanumeric index name, e.g. 'LQ45'.",
        )
    return index


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_ip(self, request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()
        window_start = now - self._window
        hits = self._hits[ip]

        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= self._max:
            retry_after = int(self._window - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Slow down."},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        path = request.url.path
        if path.startswith("/docs") or path.startswith("/static"):
            csp = (
                "default-src 'none'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        else:
            csp = "default-src 'none'; frame-ancestors 'none'"
        resp.headers.setdefault("Content-Security-Policy", csp)
        resp.headers.setdefault(
            "Cache-Control", "no-store"
        )
        return resp


def safe_detail(prefix: str, exc: Exception) -> str:
    if settings.debug:
        return f"{prefix}: {exc}"
    return prefix
