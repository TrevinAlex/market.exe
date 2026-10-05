"""Supabase-backed store for per-user activity history.

Talks to Supabase's PostgREST endpoint (``{SUPABASE_URL}/rest/v1``) with the
service_role key -- server side only, never sent to the browser. Table schema:
backend/supabase/schema.sql.

If SUPABASE_URL / SUPABASE_SERVICE_KEY are not set, history is disabled:
``record`` is a no-op and ``enabled`` is False (the API returns 503).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("market.exe.history")

TABLE = "user_history"
KINDS = ("company", "simulation")


def _project_root(url: str) -> str:
    """Accept both 'https://x.supabase.co' and the REST URL
    'https://x.supabase.co/rest/v1/' (as copied from the dashboard)."""
    url = url.strip().rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return url


def rest_url(url: str, table: str) -> str:
    return f"{_project_root(url)}/rest/v1/{table}" if url else ""


def supabase_client(
    key: str, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    headers = {"apikey": key, "Content-Type": "application/json"}
    # New-format keys (sb_secret_...) are not JWTs: PostgREST rejects them
    # in the Authorization header (PGRST301), so send them as apikey only.
    # Legacy service_role keys are JWTs ("eyJ...") and go in both.
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return httpx.AsyncClient(timeout=10, transport=transport, headers=headers)


class HistoryStore:
    def __init__(
        self,
        url: str,
        service_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = rest_url(url, TABLE)
        self._key = service_key
        self._transport = transport  # injectable for tests

    @property
    def enabled(self) -> bool:
        return bool(self._base and self._key)

    def _client(self) -> httpx.AsyncClient:
        return supabase_client(self._key, self._transport)

    async def record(
        self, user_uid: str, kind: str, symbol: str, params: dict, result: dict
    ) -> None:
        """Insert one history row. Never raises -- history must not break the
        request it is attached to (it runs as a background task)."""
        if not self.enabled:
            return
        row = {
            "user_uid": user_uid,
            "kind": kind,
            "symbol": symbol,
            "params": params,
            "result": result,
        }
        try:
            async with self._client() as c:
                r = await c.post(self._base, json=row, headers={"Prefer": "return=minimal"})
                r.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("History insert failed: %s", e)

    async def list(
        self, user_uid: str, limit: int = 50, offset: int = 0, kind: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """Return (rows newest-first, total count) for one user."""
        params = {
            "select": "id,kind,symbol,params,result,created_at",
            "user_uid": f"eq.{user_uid}",
            "order": "created_at.desc,id.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        if kind:
            params["kind"] = f"eq.{kind}"
        async with self._client() as c:
            r = await c.get(self._base, params=params, headers={"Prefer": "count=exact"})
            r.raise_for_status()
        # Content-Range: "0-9/42" or "*/0"
        total = int(r.headers.get("content-range", "*/0").rsplit("/", 1)[-1] or 0)
        return r.json(), total

    async def delete(self, user_uid: str, entry_id: int | None = None) -> int:
        """Delete one entry (or all, if entry_id is None) owned by the user.
        Returns the number of rows removed."""
        params = {"user_uid": f"eq.{user_uid}", "select": "id"}
        if entry_id is not None:
            params["id"] = f"eq.{entry_id}"
        async with self._client() as c:
            r = await c.delete(self._base, params=params, headers={"Prefer": "return=representation"})
            r.raise_for_status()
        return len(r.json())


history_store = HistoryStore(settings.supabase_url, settings.supabase_service_key)
