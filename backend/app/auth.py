from __future__ import annotations

import base64
import logging
import secrets
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import settings

log = logging.getLogger("market.exe.auth")

_SECRET = (settings.auth_secret or secrets.token_urlsafe(32)).encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


_failures: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def guard_login_attempt(request: Request) -> str:
    ip = _client_ip(request)
    now = time.time()
    hits = _failures[ip]
    while hits and hits[0] < now - settings.login_window_seconds:
        hits.popleft()
    if len(hits) >= settings.login_max_failures:
        retry = int(settings.login_window_seconds - (now - hits[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="Too many failed logins. Try again later.",
            headers={"Retry-After": str(retry)},
        )
    return ip


def record_failure(ip: str) -> None:
    _failures[ip].append(time.time())
    log.warning("Failed login attempt from %s", ip)


def clear_failures(ip: str) -> None:
    _failures.pop(ip, None)
