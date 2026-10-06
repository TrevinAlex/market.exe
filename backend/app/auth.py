"""Admin login + signed bearer tokens for the MARKET.EXE API.

The app itself is public: anyone can view scores, the heatmap and simulations
without logging in. Only admin/edit routes are protected.

Flow
----
1. An admin POSTs APP_PASSWORD to /api/admin/login.
2. On success they get a short-lived bearer token (stateless, HMAC-SHA256 signed).
3. Admin routes (``dependencies=admin_only`` in main.py) require
   ``Authorization: Bearer <token>``.

If APP_PASSWORD is not set, admin login is disabled and every admin route
returns 401 -- it fails closed, never open.

Stdlib only -- no JWT dependency. Tokens are signed with AUTH_SECRET combined
with the password, so changing APP_PASSWORD (or AUTH_SECRET) instantly
invalidates every token already issued.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

log = logging.getLogger("market.exe.auth")

_SECRET = (settings.auth_secret or secrets.token_urlsafe(32)).encode()
_SIGNING_KEY = hashlib.sha256(_SECRET + b"|" + settings.app_password.encode()).digest()

_bearer = HTTPBearer(auto_error=False, description="Token from POST /api/auth/login")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SIGNING_KEY, payload.encode(), hashlib.sha256).digest())


def issue_token(now: float | None = None) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    ttl = settings.auth_token_ttl_seconds
    payload = _b64(json.dumps({"exp": int((time.time() if now is None else now) + ttl)}).encode())
    return f"{payload}.{_sign(payload)}", ttl


def verify_token(token: str, now: float | None = None) -> bool:
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(sig, _sign(payload)):
        return False
    try:
        exp = int(json.loads(_unb64(payload))["exp"])
    except (ValueError, KeyError, TypeError):
        return False
    return exp > (time.time() if now is None else now)


def check_password(candidate: str) -> bool:
    if not settings.app_password:
        return False
    want = hashlib.sha256(settings.app_password.encode()).digest()
    got = hashlib.sha256(candidate.encode()).digest()
    return hmac.compare_digest(want, got)


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """FastAPI dependency: 401 unless a valid admin bearer token is present."""
    if (
        not settings.app_password
        or creds is None
        or creds.scheme.lower() != "bearer"
        or not verify_token(creds.credentials)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


_failures: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def guard_login_attempt(request: Request) -> str:
    """Raise 429 if this IP has too many recent failures. Returns the IP."""
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
