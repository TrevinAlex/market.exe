"""Basic security layer for the MARKET.EXE backend.

Dependency-free (stdlib + starlette/fastapi only). Provides:

* Input validation   -- validate_symbol / validate_index reject anything that
                        isn't a clean ticker/index, so nothing crafted reaches
                        the upstream Sectors query.
* Rate limiting      -- RateLimitMiddleware, a fixed-window per-IP limiter that
                        protects the CPU-heavy simulation and your Sectors
                        credit grant from abuse.
* Security headers   -- SecurityHeadersMiddleware adds the standard hardening
                        headers to every response.

These are demo-grade protections appropriate for a hackathon backend. For a
real deployment you would move rate limiting to a shared store (Redis) and put
auth / a gateway in front; see README security notes.
"""
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
    """Return the symbol if it is a valid IDX ticker, else 400.

    Blocks path/query injection: the symbol is interpolated into the upstream
    Sectors URL, so only a strict ticker shape is allowed through.
    """
    if not symbol or not _SYMBOL_RE.match(symbol):
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol. Expected a 4-letter IDX ticker, e.g. 'BBCA'.",
        )
    return symbol


def validate_index(index: str | None) -> str | None:
    """Return the index if valid, None if omitted, else 400.

    The index is interpolated into the Sectors `where` clause, so it must be a
    plain alphanumeric token -- no quotes, brackets, or operators.
    """
    if index is None:
        return None
    if not _INDEX_RE.match(index):
        raise HTTPException(
            status_code=400,
            detail="Invalid index. Expected an alphanumeric index name, e.g. 'LQ45'.",
        )
    return index




class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP rate limiter (in-process).

    Good enough for a single-instance hackathon demo. Not shared across
    workers/instances -- document that limitation rather than pretend otherwise.
    """

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
    """Add standard hardening headers to every response."""

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
    """Return a client-safe error string.

    In debug mode include the exception text; otherwise return a generic
    message so upstream error bodies (which can contain key-adjacent info)
    are never echoed to clients.
    """
    if settings.debug:
        return f"{prefix}: {exc}"
    return prefix
