"""Supabase-backed store for each user's pinned stocks (watchlist).

Table ``user_pins`` (backend/supabase/schema.sql): primary key
(user_uid, symbol), so pinning the same stock twice is a no-op.
Same credentials / transport rules as app/services/history.py.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.services.history import rest_url, supabase_client

TABLE = "user_pins"


class PinLimitError(Exception):
    """Raised when a user already has the maximum number of pins."""


class PinStore:
    def __init__(
        self,
        url: str,
        service_key: str,
        max_pins: int = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = rest_url(url, TABLE)
        self._key = service_key
        self.max_pins = max_pins
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._base and self._key)

    def _client(self) -> httpx.AsyncClient:
        return supabase_client(self._key, self._transport)

    async def list(self, user_uid: str) -> list[dict[str, Any]]:
        """All pins for a user, oldest first: [{symbol, created_at}]."""
        params = {
            "select": "symbol,created_at",
            "user_uid": f"eq.{user_uid}",
            "order": "created_at.asc,symbol.asc",
        }
        async with self._client() as c:
            r = await c.get(self._base, params=params)
            r.raise_for_status()
        return r.json()

    async def add(self, user_uid: str, symbol: str) -> bool:
        """Pin a symbol. Returns False if it was already pinned.
        Raises PinLimitError when the user is at max_pins."""
        pins = await self.list(user_uid)
        if any(p["symbol"] == symbol for p in pins):
            return False
        if len(pins) >= self.max_pins:
            raise PinLimitError
        async with self._client() as c:
            r = await c.post(
                self._base,
                params={"on_conflict": "user_uid,symbol"},
                json={"user_uid": user_uid, "symbol": symbol},
                headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
            )
            r.raise_for_status()
        return True

    async def remove(self, user_uid: str, symbol: str) -> bool:
        """Unpin a symbol. Returns False if it was not pinned."""
        params = {"user_uid": f"eq.{user_uid}", "symbol": f"eq.{symbol}", "select": "symbol"}
        async with self._client() as c:
            r = await c.delete(self._base, params=params, headers={"Prefer": "return=representation"})
            r.raise_for_status()
        return len(r.json()) > 0


pin_store = PinStore(settings.supabase_url, settings.supabase_service_key, settings.max_pins)
