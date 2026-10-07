from __future__ import annotations

from typing import Any

import numpy as np

LIQUIDITY_DAYS = 20


def liquidity_from_rows(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    vals, vols = [], []
    for r in (rows or [])[-LIQUIDITY_DAYS:]:
        try:
            close, volume = float(r["close"]), float(r["volume"])
        except (KeyError, TypeError, ValueError):
            continue
        if close > 0 and volume >= 0:
            vals.append(close * volume)
            vols.append(volume)
    if not vals:
        return None
    return {
        "avg_daily_value": round(float(np.median(vals)), 0),
        "avg_daily_volume": round(float(np.median(vols)), 0),
        "days": len(vals),
    }
