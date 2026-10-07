from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("market.exe.history")

TABLE = "user_history"
KINDS = ("company", "simulation")


def _project_root(url: str) -> str:
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
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._base and self._key)

    def _client(self) -> httpx.AsyncClient:
        return supabase_client(self._key, self._transport)

    async def record(
        self, user_uid: str, kind: str, symbol: str, params: dict, result: dict
    ) -> None:
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
        total = int(r.headers.get("content-range", "*/0").rsplit("/", 1)[-1] or 0)
        return r.json(), total

    async def delete(self, user_uid: str, entry_id: int | None = None) -> int:
        params = {"user_uid": f"eq.{user_uid}", "select": "id"}
        if entry_id is not None:
            params["id"] = f"eq.{entry_id}"
        async with self._client() as c:
            r = await c.delete(self._base, params=params, headers={"Prefer": "return=representation"})
            r.raise_for_status()
        return len(r.json())


history_store = HistoryStore(settings.supabase_url, settings.supabase_service_key)
