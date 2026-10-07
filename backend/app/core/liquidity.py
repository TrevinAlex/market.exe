"""Exit liquidity: how easily a position can be sold.

Uses the volume already in the Sectors daily rows the simulation fetches, so
it costs no extra credits. The cost estimate itself is done per amount in the
frontend (positionRisk.ts) with the square-root market-impact rule.
"""
from __future__ import annotations

from typing import Any

import numpy as np

LIQUIDITY_DAYS = 20


def liquidity_from_rows(rows: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Typical daily trading over the last LIQUIDITY_DAYS days.

    Median rather than mean, so one block trade doesn't make a thin stock look
    liquid. None when there are no usable rows.
    """
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
