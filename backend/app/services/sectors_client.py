"""Wrapper around the Sectors Financial API v2.

Two data sources are used, each for what it is best at:

* Company Report  (/v2/company/report/{symbol})
    Rich, nested, reliable per-company fundamentals. Used for single-company
    scoring and the simulation. We request only the 4 sections the scorer needs
    (overview, valuation, future, financials) = 4 credits per company.

* Company Screener (/v2/companies/)
    Cheap ranking across many companies (1 credit/call). Used for the screen
    list and the sector heatmap. Scoring fields are surfaced into query_values
    by referencing them in order_by.

Responses are cached in-process for CACHE_TTL seconds so repeated dev requests
do not burn the hackathon credit grant.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

import httpx

from app.config import settings

REPORT_SECTIONS = ["overview", "valuation", "future", "financials"]

SCREEN_SCORING_FIELDS = [
    "last_close_price",
    "daily_close_change",
    "52_w_high_price",
    "52_w_low_price",
    "pe_ttm",
    "der_mrq",
    "roe_ttm",
    "roa_ttm",
    "sector",
    "sub_sector",
]


def _surface_clause() -> str:
    parts = [f"({f} IS NULL or {f} IS NOT NULL)" for f in SCREEN_SCORING_FIELDS]
    return " and ".join(parts)


class SectorsClient:
    def __init__(self) -> None:
        self._base = settings.sectors_base_url.rstrip("/")
        self._headers = {"Authorization": settings.sectors_api_key}
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cache_get(self, key: str) -> Any | None:
        hit = self._cache.get(key)
        if not hit:
            return None
        ts, value = hit
        if time.time() - ts > settings.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time(), value)

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        cache_key = f"{path}?{sorted(params.items())}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers, params=params)
            resp.raise_for_status()
            data = resp.json()
        self._cache_set(cache_key, data)
        return data

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """Report endpoint accepts a bare 4-letter ticker; strip any .JK."""
        return symbol.upper().replace(".JK", "").strip()

    async def company_report(self, symbol: str) -> dict[str, Any] | None:
        """Fetch the 4 scoring sections of a company report. None if 404."""
        sym = self._normalize_symbol(symbol)
        params = {"sections": ",".join(REPORT_SECTIONS)}
        try:
            data = await self._get(f"/company/report/{sym}/", params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        if isinstance(data, dict) and data.get("error"):
            return None
        return data

    async def daily_closes(self, symbol: str) -> list[float]:
        """Last 90 calendar days (~60 trading days) of closes, oldest first.

        1 credit (cached). Feeds the volatility model in the simulation.
        """
        sym = self._normalize_symbol(symbol)
        end = date.today()
        params = {"start": (end - timedelta(days=90)).isoformat(), "end": end.isoformat()}
        data = await self._get(f"/daily/{sym}/", params)
        rows = data if isinstance(data, list) else []
        rows = sorted((r for r in rows if isinstance(r, dict) and r.get("close")), key=lambda r: r.get("date", ""))
        return [float(r["close"]) for r in rows]

    async def corporate_actions(self, symbol: str) -> dict[str, Any]:
        """Dividends, AGMs, splits, rights issues... for one company. 1 credit (cached)."""
        sym = self._normalize_symbol(symbol)
        data = await self._get(f"/company/corporate-actions/{sym}/", {})
        if isinstance(data, dict):
            return data.get("corporate_actions") or {}
        return {}

    async def screen(
        self,
        where: str | None = None,
        order_by: str = "-market_cap",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Structured screener query -> raw results list.

        Scoring fields the frontend list needs are surfaced by ordering on them
        and setting include_query_values; callers merge query_values into the
        row before scoring.
        """
        params: dict[str, Any] = {
            "order_by": order_by,
            "limit": min(limit, 200),
            "offset": offset,
            "include_query_values": "true",
        }
        if where:
            params["where"] = where
        data = await self._get("/companies/", params)
        results = data.get("results", []) if isinstance(data, dict) else []
        for row in results:
            qv = row.get("query_values")
            if isinstance(qv, dict):
                for k, v in qv.items():
                    row.setdefault(k, v)
        return results

    async def screen_scored(
        self,
        base_where: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Screen companies with all scoring fields surfaced into each row.

        `base_where` is the real filter (e.g. an index restriction); the scoring
        fields are appended as benign always-true clauses so they appear in
        query_values. Rows are returned flattened and ready for score_company.
        """
        surface = _surface_clause()
        where = f"({base_where}) and {surface}" if base_where else surface
        return await self.screen(where=where, order_by="-market_cap", limit=limit, offset=offset)


sectors_client = SectorsClient()
