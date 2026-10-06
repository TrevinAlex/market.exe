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


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def explain_inputs(c: dict[str, Any]) -> dict[str, dict[str, str | None]]:
    """The raw input behind each sub-score and the rule that maps it to points.

    Lets the UI show "ROE 18.0% -> 14.4 / 20 (full marks at 25%)" so users can
    check the score instead of taking it on faith. The rule text mirrors the
    score_* functions above; keep the two in sync.
    """
    pe = _num(c.get("pe_ttm"))
    der = _num(c.get("der_mrq"))
    roe = _num(c.get("roe_ttm"))
    roa = _num(c.get("roa_ttm"))
    price = _num(c.get("last_close_price"))
    hi = _num(c.get("52_w_high_price"))
    lo = _num(c.get("52_w_low_price"))
    chg = _num(c.get("daily_close_change"))

    momentum_input = None
    if price is not None and hi is not None and lo is not None and hi > lo:
        position = _clamp((price - lo) / (hi - lo))
        momentum_input = f"{position * 100:.0f}% of 52-week range"
        if chg is not None:
            momentum_input += f", today {chg * 100:+.1f}%"

    return {
        "valuation": {
            "input": f"P/E {pe:.1f}" if pe is not None and pe > 0 else None,
            "rule": "Full marks at P/E 5 or lower, zero at 25 or higher",
        },
        "momentum": {
            "input": momentum_input,
            "rule": "Up to 14 pts for sitting near 65% of the 52-week range, up to 6 pts for today's move",
        },
        "debt": {
            "input": f"Debt/equity {der:.2f}" if der is not None else None,
            "rule": "Full marks at 0, zero at 2.5 or higher",
        },
        "quality": {
            "input": f"ROE {_pct(roe)}" if roe is not None else None,
            "rule": "Zero at 0%, full marks at 25% or higher",
        },
        "profitability": {
            "input": f"ROA {_pct(roa)}" if roa is not None else None,
            "rule": "Zero at 0%, full marks at 15% or higher",
        },
    }


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
    breakdown: dict[str, dict[str, str | None]] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sub_scores_normalized"] = self.sub_scores.normalized()
        return d


def _year(value: Any) -> int | None:
    try:
        return int(str(value)[:4])
    except (TypeError, ValueError):
        return None


def fundamentals_history(report: dict[str, Any], max_years: int = 8) -> dict[str, Any]:
    """Yearly fundamentals and the four fundamental sub-scores, per fiscal year.

    Uses data already inside the Company Report (financials.historical_financial_ratio
    and valuation.historical_valuation), so it costs no extra API credits. Momentum
    is left out: it needs a past price range, which the report doesn't carry per year.

    The score is the four sub-scores rescaled to 0-100. It DESCRIBES how the
    company's numbers have moved; it is not a forecast (see the report card).
    """
    financials = report.get("financials") or {}
    valuation = report.get("valuation") or {}

    pe_by_year: dict[int, float | None] = {}
    for row in valuation.get("historical_valuation") or []:
        y = _year(row.get("year")) if isinstance(row, dict) else None
        if y is not None:
            pe_by_year[y] = _num(row.get("pe"))

    by_year: dict[int, dict[str, Any]] = {}
    for row in financials.get("historical_financial_ratio") or []:
        y = _year(row.get("year")) if isinstance(row, dict) else None
        if y is None:
            continue
        prof = row.get("profitability") or {}
        lev = row.get("leverage") or {}
        by_year[y] = {
            "roe": _num(prof.get("roe")),
            "roa": _num(prof.get("roa")),
            "der": _num(lev.get("debt_to_equity_ratio")),
        }

    years: list[dict[str, Any]] = []
    for y in sorted(by_year)[-max_years:]:
        r = by_year[y]
        c = {"roe_ttm": r["roe"], "roa_ttm": r["roa"], "der_mrq": r["der"], "pe_ttm": pe_by_year.get(y)}
        parts = [score_valuation(c), score_debt(c), score_quality(c), score_profitability(c)]
        known = sum(cf for _, cf in parts)
        years.append({
            "year": y,
            "roe": r["roe"],
            "roa": r["roa"],
            "der": r["der"],
            "pe": pe_by_year.get(y),
            "valuation": parts[0][0],
            "debt": parts[1][0],
            "quality": parts[2][0],
            "profitability": parts[3][0],
            # 4 sub-scores x 20 = 80 points, rescaled to 0-100. None when no input is known.
            "score": round(sum(s for s, _ in parts) * 100 / 80, 1) if known else None,
        })

    return {"years": years, "trend": _trend(years)}


def _trend(years: list[dict[str, Any]]) -> str | None:
    """Latest year's score vs the average of the up-to-3 years before it."""
    scored = [y["score"] for y in years if y["score"] is not None]
    if len(scored) < 2:
        return None
    prior = scored[-4:-1]
    delta = scored[-1] - sum(prior) / len(prior)
    if delta >= 5:
        return "improving"
    if delta <= -5:
        return "deteriorating"
    return "stable"


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
        breakdown=explain_inputs(c),
    )
