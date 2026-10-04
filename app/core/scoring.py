"""The scoring engine: raw Sectors fields -> derived health score + regime.

This is the module that makes the project qualify for the Market Intelligence
track. None of the outputs here (sub-scores, composite score, regime label)
exist in the Sectors API; they are DERIVED by normalising and combining raw
fields.

Each of the five dimensions returns a sub-score in [0, 20]. The composite is
their sum in [0, 100]. A regime label is mapped from the composite.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _num(value: Any) -> float | None:
    """Coerce a raw field to float, tolerating None / strings / missing."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def flatten_report(report: dict[str, Any]) -> dict[str, Any]:
    """Flatten a nested Company Report into the flat row score_company expects.

    The report groups fields into sections (overview, valuation, future,
    financials). We pull the specific fields each scoring dimension needs and
    expose them under the same flat keys the screener rows use, so the scoring
    math has a single input shape regardless of source.
    """
    overview = report.get("overview") or {}
    valuation = report.get("valuation") or {}
    future = report.get("future") or {}
    financials = report.get("financials") or {}

    flat: dict[str, Any] = {
        "symbol": (report.get("symbol") or "?"),
        "company_name": report.get("company_name") or "?",
        "sector": overview.get("sector"),
        "sub_sector": overview.get("sub_sector"),
        "last_close_price": overview.get("last_close_price") or valuation.get("last_close_price"),
        "daily_close_change": overview.get("daily_close_change") or valuation.get("daily_close_change"),
        "market_cap": overview.get("market_cap"),
    }

    # 52-week range lives as {date: price} dicts under overview.
    def _first_val(d: Any) -> float | None:
        if isinstance(d, dict) and d:
            return _num(next(iter(d.values())))
        return None

    flat["52_w_high_price"] = _first_val(overview.get("52_w_high"))
    flat["52_w_low_price"] = _first_val(overview.get("52_w_low"))

    # Valuation: forward_pe is the report's PE proxy (pe_ttm not in report).
    flat["pe_ttm"] = valuation.get("forward_pe")

    # Latest-year ratios from historical_financial_ratio (take the last entry).
    ratios = financials.get("historical_financial_ratio") or []
    latest = ratios[-1] if ratios else {}
    prof = (latest.get("profitability") or {})
    lev = (latest.get("leverage") or {})
    flat["roe_ttm"] = prof.get("roe")
    flat["roa_ttm"] = prof.get("roa")
    flat["der_mrq"] = lev.get("debt_to_equity_ratio")

    # Analyst forecast momentum (future section) -> stash for optional use.
    growth = future.get("company_growth_forecasts") or []
    flat["forecast_eps_growth"] = (growth[0].get("eps_growth") if growth else None)

    return flat


# ---------------------------------------------------------------------------
# Individual dimensions. Each returns (sub_score_0_to_20, confidence_0_to_1).
# Confidence drops when inputs are missing, so the UI can show which signals
# are backed by data.
# ---------------------------------------------------------------------------

def score_valuation(c: dict[str, Any]) -> tuple[float, float]:
    """Cheaper than a reasonable PE band = higher score.

    We lack per-row peer averages in the screener's default projection, so we
    score against an absolute IDX-reasonable PE band (5-25). Below 5 may be a
    value trap; above 25 is expensive.
    """
    pe = _num(c.get("pe_ttm"))
    if pe is None or pe <= 0:
        return 10.0, 0.0  # neutral, no confidence
    # map PE 5 -> best, 25 -> worst
    norm = _clamp((25.0 - pe) / (25.0 - 5.0))
    return round(norm * 20, 2), 1.0


def score_momentum(c: dict[str, Any]) -> tuple[float, float]:
    """Position within the 52-week range + today's drift."""
    price = _num(c.get("last_close_price"))
    hi = _num(c.get("52_w_high_price"))
    lo = _num(c.get("52_w_low_price"))
    chg = _num(c.get("daily_close_change")) or 0.0
    if price is None or hi is None or lo is None or hi <= lo:
        return 10.0, 0.0
    position = _clamp((price - lo) / (hi - lo))  # 0 = at low, 1 = at high
    # Mid-upper range with positive drift is healthiest; extreme top = frothy.
    base = 1.0 - abs(position - 0.65) / 0.65  # peaks around 65% of range
    drift_bonus = _clamp(0.5 + chg * 10, 0, 1) * 0.3
    norm = _clamp(base * 0.7 + drift_bonus)
    return round(norm * 20, 2), 1.0


def score_debt(c: dict[str, Any]) -> tuple[float, float]:
    """Lower leverage = higher score. Uses debt-to-equity (most recent qtr)."""
    der = _num(c.get("der_mrq"))
    if der is None:
        return 10.0, 0.0
    # DER 0 -> best, 2.5+ -> worst (financials run higher; this is a floor model)
    norm = _clamp((2.5 - der) / 2.5)
    return round(norm * 20, 2), 1.0


def score_quality(c: dict[str, Any]) -> tuple[float, float]:
    """Return on equity as a profitability-quality proxy."""
    roe = _num(c.get("roe_ttm"))
    if roe is None:
        return 10.0, 0.0
    # ROE 0 -> worst, 0.25 (25%) -> best
    norm = _clamp(roe / 0.25)
    return round(norm * 20, 2), 1.0


def score_profitability(c: dict[str, Any]) -> tuple[float, float]:
    """Return on assets as a capital-efficiency proxy (second quality lens)."""
    roa = _num(c.get("roa_ttm"))
    if roa is None:
        return 10.0, 0.0
    norm = _clamp(roa / 0.15)  # ROA 15% -> best
    return round(norm * 20, 2), 1.0


REGIME_BANDS = [
    (70, "Accumulation", "green"),
    (50, "Recovery", "yellow"),
    (30, "Distribution", "amber"),
    (0, "Stress", "red"),
]


def regime_for(score: float) -> tuple[str, str]:
    for threshold, label, color in REGIME_BANDS:
        if score >= threshold:
            return label, color
    return "Stress", "red"


@dataclass
class SubScores:
    valuation: float
    momentum: float
    debt: float
    quality: float
    profitability: float

    def normalized(self) -> dict[str, float]:
        """Each sub-score as a 0-1 value, for the simulation calibrator."""
        return {k: round(v / 20.0, 4) for k, v in asdict(self).items()}


@dataclass
class ScoreResult:
    symbol: str
    company_name: str
    sector: str | None
    sub_sector: str | None
    composite: float
    regime: str
    color: str
    sub_scores: SubScores
    confidence: float
    last_close_price: float | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sub_scores_normalized"] = self.sub_scores.normalized()
        return d


def score_company(c: dict[str, Any]) -> ScoreResult:
    val, cf1 = score_valuation(c)
    mom, cf2 = score_momentum(c)
    debt, cf3 = score_debt(c)
    qual, cf4 = score_quality(c)
    prof, cf5 = score_profitability(c)

    subs = SubScores(valuation=val, momentum=mom, debt=debt, quality=qual, profitability=prof)
    composite = round(val + mom + debt + qual + prof, 2)
    label, color = regime_for(composite)
    confidence = round((cf1 + cf2 + cf3 + cf4 + cf5) / 5.0, 2)

    return ScoreResult(
        symbol=c.get("symbol", "?"),
        company_name=c.get("company_name", "?"),
        sector=c.get("sector"),
        sub_sector=c.get("sub_sector"),
        composite=composite,
        regime=label,
        color=color,
        sub_scores=subs,
        confidence=confidence,
        last_close_price=_num(c.get("last_close_price")),
    )
