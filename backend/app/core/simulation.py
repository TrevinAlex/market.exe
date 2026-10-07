"""Agent-based Monte Carlo simulation.

The 'What Happens Next' layer. 1000 heterogeneous agents trade a single stock
over N days. Their behavioural mix is NOT random: it is calibrated from the
stock's normalised sub-scores produced by the scoring engine, so a high-debt,
weak-momentum stock gets more panic sellers and a cheap, strong-momentum stock
gets more buyers.

Runs the day-loop `runs` times (Monte Carlo) and reports the distribution of
outcomes as percentile bands, which is the actual predictive output.

Vectorised with numpy: 500 runs x 30 days x 1000 agents completes well under a
second, so this can run on-demand per stock without burning API credits (it
calls no API at all).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np


@dataclass
class AgentMix:
    """Fractions of the 1000-agent population, derived from sub-scores."""
    panic_sellers: float
    momentum_buyers: float
    value_buyers: float
    profit_takers: float
    passive_holders: float

    def as_dict(self) -> dict[str, float]:
        return {
            "panic_sellers": round(self.panic_sellers, 3),
            "momentum_buyers": round(self.momentum_buyers, 3),
            "value_buyers": round(self.value_buyers, 3),
            "profit_takers": round(self.profit_takers, 3),
            "passive_holders": round(self.passive_holders, 3),
        }


def calibrate_agents(sub_scores_norm: dict[str, float]) -> AgentMix:
    """Translate normalised 0-1 sub-scores into an agent population mix.

    Rationale encoded here IS the methodology judges can interrogate:
      - weak debt score  -> more panic sellers
      - strong momentum  -> more momentum buyers
      - cheap valuation  -> more value buyers
      - weak quality     -> more profit takers (less conviction to hold)
    """
    debt = sub_scores_norm.get("debt", 0.5)
    momentum = sub_scores_norm.get("momentum", 0.5)
    valuation = sub_scores_norm.get("valuation", 0.5)
    quality = sub_scores_norm.get("quality", 0.5)

    panic = 0.10 + (1 - debt) * 0.30
    momo = 0.08 + momentum * 0.27
    value = 0.08 + valuation * 0.24
    profit = 0.08 + (1 - quality) * 0.15

    raw = np.array([panic, momo, value, profit])
    passive = max(0.05, 1.0 - raw.sum())
    full = np.append(raw, passive)
    full = full / full.sum()

    return AgentMix(*[float(x) for x in full])


DEFAULT_DAILY_VOL = 0.008
MIN_DAILY_VOL = 0.005
MAX_DAILY_VOL = 0.08

_RANGE_TO_SIGMA = float(np.sqrt(8 * 252 / np.pi))


def estimate_daily_vol(high_52w: float | None, low_52w: float | None) -> float | None:
    """Daily volatility estimated from the 52-week high/low.

    Uses only fields the company report already has, so it costs no extra API
    credits. Returns None when the range is missing or invalid; the result is
    clamped to a sane band so one bad data point can't blow up the simulation.
    """
    try:
        hi, lo = float(high_52w), float(low_52w)
    except (TypeError, ValueError):
        return None
    if not (hi > lo > 0):
        return None
    sigma = float(np.log(hi / lo)) / _RANGE_TO_SIGMA
    return min(MAX_DAILY_VOL, max(MIN_DAILY_VOL, sigma))


_VOL_MODEL = {
    "intercept": -1.2238,
    "lv_range": 0.1838,
    "lv5": 0.0608,
    "lv20": 0.2776,
    "lv60": 0.1206,
    "labs_r20": 0.0368,
}
MIN_CLOSES_FOR_MODEL = 22


def predict_daily_vol(
    closes: list[float] | None,
    high_52w: float | None,
    low_52w: float | None,
) -> tuple[float | None, str]:
    """Best available daily-volatility forecast and the method used.

    Returns (vol, "ml") when enough daily closes are given (oldest first),
    else (range estimate, "range"), else (None, "default").
    """
    v_range = estimate_daily_vol(high_52w, low_52w)
    px = np.array([c for c in (closes or []) if c and c > 0], dtype=float)
    if len(px) >= MIN_CLOSES_FOR_MODEL:
        r = np.diff(np.log(px))[-60:]
        v5, v20, v60 = (float(np.std(r[-n:])) for n in (5, 20, 60))
        if min(v5, v20, v60) > 0:
            vr = v_range if v_range is not None else v60
            m = _VOL_MODEL
            log_vol = (m["intercept"] + m["lv_range"] * np.log(vr) + m["lv5"] * np.log(v5)
                       + m["lv20"] * np.log(v20) + m["lv60"] * np.log(v60)
                       + m["labs_r20"] * np.log(abs(np.log(px[-1] / px[-21])) + 0.01))
            return min(MAX_DAILY_VOL, max(MIN_DAILY_VOL, float(np.exp(log_vol)))), "ml"
    if v_range is not None:
        return v_range, "range"
    return None, "default"


_AGENT_MEAN_IMPACT = (-0.003, 0.0025, 0.00175, -0.00125)

DEFAULT_DRIFT_SCALE = 0.0


def agent_expected_drift(mix: AgentMix) -> float:
    """Expected daily return the agent mix pushes the price by."""
    fr = (mix.panic_sellers, mix.momentum_buyers, mix.value_buyers, mix.profit_takers)
    return float(sum(f * i for f, i in zip(fr, _AGENT_MEAN_IMPACT)))


def upcoming_dividends(
    corporate_actions: dict[str, Any] | None,
    horizon_days: int,
    today: date | None = None,
) -> list[tuple[int, float]]:
    """(trading_day, amount) for dividends whose ex-date falls inside the horizon.

    Reads Sectors corporate actions: both ``upcoming_dividend`` and future
    entries of ``dividend``. Trading days are counted as weekdays after today
    (IDX holidays ignored, so a date may land a day or two early).
    """
    ca = corporate_actions or {}
    today = today or date.today()
    items: list[dict[str, Any]] = []
    for key in ("upcoming_dividend", "dividend"):
        v = ca.get(key)
        if isinstance(v, dict):
            items.append(v)
        elif isinstance(v, list):
            items.extend(x for x in v if isinstance(x, dict))
    out: dict[str, float] = {}
    for it in items:
        ex, amt = it.get("ex_date"), it.get("dividend_amount") or it.get("amount")
        try:
            ex_d = date.fromisoformat(str(ex)[:10])
            amount = float(amt)
        except (TypeError, ValueError):
            continue
        if ex_d > today and amount > 0:
            out[ex_d.isoformat()] = amount
    events = []
    for ex, amount in out.items():
        day = int(np.busday_count(today, date.fromisoformat(ex))) + 1
        if 1 <= day <= horizon_days:
            events.append((day, amount))
    return sorted(events)


# Price-reacting agents: how many trading days of the simulated path the agents
# look back over when deciding whether the stock is "falling" or "rising".
REACTION_LOOKBACK = 5
# Upper bound on the share of active (non-passive) agents after reacting.
MAX_ACTIVE_SHARE = 0.95


def react_mix(
    base: np.ndarray,
    z: np.ndarray,
    herding: float,
    contrarian: float,
) -> np.ndarray:
    """Per-run agent shares after reacting to the recent simulated move.

    ``base`` is (4,) = panic, momentum, value, profit-taker shares; ``z`` is
    (runs,) = the move over the last REACTION_LOOKBACK days in units of
    expected volatility (z = -1: a typical-sized fall). Returns (runs, 4).

      herding     trend followers: falls recruit panic sellers, rises recruit
                  momentum buyers (positive feedback)
      contrarian  falls recruit value buyers, rises recruit profit takers
                  (negative feedback)
    """
    down, up = np.maximum(-z, 0.0), np.maximum(z, 0.0)
    mult = np.stack([
        1 + herding * down,      # panic sellers
        1 + herding * up,        # momentum buyers
        1 + contrarian * down,   # value buyers
        1 + contrarian * up,     # profit takers
    ], axis=1)
    shares = base[None, :] * mult
    total = shares.sum(axis=1, keepdims=True)
    return shares * np.minimum(1.0, MAX_ACTIVE_SHARE / total)


@dataclass(frozen=True)
class Scenario:
    """A stress scenario: a changed crowd, calibrated to a real IDX episode.

    For the first ``length`` trading days the agent mix gets ``shift`` added
    (panic, momentum, value, profit-taker shares), agents herd with strength
    ``herding``, and market noise is ``vol_mult`` times the stock's normal
    volatility. The crowd's net push is scaled so that, before herding, it moves
    the price by ``intensity`` daily volatilities per day (negative = selling),
    or by ``intensity`` as a plain daily return when ``flat`` is set. Which form
    each scenario uses was chosen by the calibration: in the 2020 crash calm
    and volatile stocks fell about equally (flat), while in the 2020 rally the
    volatile ones rose more (volatility-scaled). The numbers come from
    backtest/scenario_calibration.py, fitted to how LQ45 stocks actually moved.
    """
    id: str
    label: str
    shift: tuple[float, float, float, float]
    intensity: float
    vol_mult: float
    herding: float
    length: int
    window: str
    description: str
    fit_inside_p10_p90: float
    fit_n: int
    historical_median_return_pct: float
    # True: `intensity` is a fixed daily return for every stock, not a number
    # of the stock's own daily volatilities.
    flat: bool = False


# Calibrated by backtest/scenario_calibration.py (see results_scenarios.json):
# the worst and best 30-trading-day stretches for LQ45 stocks since 2017, each
# fitted on the 40 stocks listed at the time. These are in-sample fits to one
# episode each: they describe that episode, they do not predict the next one.
SCENARIOS: dict[str, Scenario] = {
    "panic_2020": Scenario(
        id="panic_2020",
        label="2020-style panic",
        shift=(0.25, -0.05, -0.04, 0.0),
        intensity=-0.0175,
        vol_mult=2.0,
        herding=0.0,
        length=30,
        window="11 Feb - 24 Mar 2020",
        description=(
            "Panic sellers flood in and daily moves get twice as wild. Sized to the COVID crash, "
            "when the median LQ45 stock fell 44% in 30 trading days, calm and volatile stocks alike."
        ),
        fit_inside_p10_p90=0.80,
        fit_n=40,
        historical_median_return_pct=-44.3,
        flat=True,
    ),
    "rally_2020": Scenario(
        id="rally_2020",
        label="2020-style rally",
        shift=(-0.05, 0.25, 0.0, -0.04),
        intensity=0.4,
        vol_mult=1.0,
        herding=0.0,
        length=30,
        window="4 Nov - 17 Dec 2020",
        description=(
            "Momentum buyers pile in. Sized to the vaccine rally, when the median LQ45 stock "
            "rose 32% in 30 trading days; more volatile stocks rose more."
        ),
        fit_inside_p10_p90=0.65,
        fit_n=40,
        historical_median_return_pct=31.6,
    ),
}


def _scenario_shares(base: np.ndarray, shift: tuple[float, float, float, float]) -> np.ndarray:
    shares = np.maximum(base + np.array(shift, dtype=float), 0.0)
    total = shares.sum()
    return shares * min(1.0, MAX_ACTIVE_SHARE / total) if total > 0 else shares


def _drift_of(shares: np.ndarray) -> float:
    return float(np.dot(shares, _AGENT_MEAN_IMPACT))


def run_simulation(
    current_price: float,
    sub_scores_norm: dict[str, float],
    runs: int = 500,
    days: int = 30,
    agents: int = 1000,
    seed: int | None = None,
    daily_vol: float | None = None,
    drift_scale: float = DEFAULT_DRIFT_SCALE,
    dividends: list[tuple[int, float]] | None = None,
    vol_method: str | None = None,
    herding: float = 0.0,
    contrarian: float = 0.0,
    scenario: Scenario | None = None,
    sample_count: int = 50,
) -> dict[str, Any]:
    """Return percentile bands + a sample of paths for charting.

    ``daily_vol``   market-noise volatility per trading day (predict_daily_vol);
                    None falls back to DEFAULT_DAILY_VOL.
    ``drift_scale`` share of the agent mix's net drift to keep (0 = none).
    ``dividends``   known (trading_day, amount_per_share) payouts inside the
                    horizon; the price drops by the amount on that ex-date.
    ``herding`` / ``contrarian``
                    price-reacting agents (see react_mix); 0 = agents ignore
                    the price, the backtested default.
    ``scenario``    a stress Scenario (see SCENARIOS); None = normal market.
    """
    if current_price is None or current_price <= 0:
        current_price = 1000.0
    vol = DEFAULT_DAILY_VOL if daily_vol is None or daily_vol <= 0 else float(daily_vol)
    divs = {}
    for day, amount in dividends or []:
        if 1 <= int(day) <= days and amount and amount > 0:
            divs[int(day)] = divs.get(int(day), 0.0) + float(amount)

    rng = np.random.default_rng(seed)
    mix = calibrate_agents(sub_scores_norm)
    drift_bias = agent_expected_drift(mix) * (1.0 - float(drift_scale))

    base_shares = np.array([
        mix.panic_sellers,
        mix.momentum_buyers,
        mix.value_buyers,
        mix.profit_takers,
    ])
    reacting = herding > 0 or contrarian > 0

    # Stress scenario: a different crowd for the first `scn_days` days, with its
    # push scaled to `intensity` daily volatilities. The health-based drift of
    # the normal mix is still removed, so only the scenario moves the price.
    scn_days = 0
    if scenario is not None:
        scn_shares = _scenario_shares(base_shares, scenario.shift)
        raw_shift = _drift_of(scn_shares) - _drift_of(base_shares)
        push = scenario.intensity if scenario.flat else scenario.intensity * vol
        scn_scale = push / raw_shift if raw_shift else 0.0
        scn_bias = _drift_of(base_shares) * scn_scale
        scn_vol = vol * scenario.vol_mult
        scn_days = min(days, scenario.length)

    paths = np.empty((runs, days + 1), dtype=np.float64)
    paths[:, 0] = current_price
    # Noise drawn up front so it is identical with and without price-reacting
    # agents for the same seed (a fair A/B comparison in the backtest).
    noise_all = rng.normal(0, vol, size=(days, runs))

    for d in range(1, days + 1):
        in_scn = d <= scn_days
        if in_scn:
            look = min(REACTION_LOOKBACK, d - 1)
            z = np.zeros(runs)
            if look > 0 and scenario.herding > 0:
                z = np.log(paths[:, d - 1] / paths[:, d - 1 - look]) / (scn_vol * np.sqrt(look))
            shares = react_mix(scn_shares, z, scenario.herding, 0.0)
        elif reacting:
            look = min(REACTION_LOOKBACK, d - 1)
            z = np.zeros(runs)
            if look > 0:
                z = np.log(paths[:, d - 1] / paths[:, d - 1 - look]) / (vol * np.sqrt(look))
            shares = react_mix(base_shares, z, herding, contrarian)
        else:
            shares = np.broadcast_to(base_shares, (runs, 4))
        t0, t1, t2, t3 = (c[:, None] for c in np.cumsum(shares, axis=1).T)

        rolls = rng.random((runs, agents))
        pressure = np.zeros((runs, agents))

        m = rolls < t0
        pressure[m] = -rng.uniform(0.001, 0.005, size=m.sum())
        m = (rolls >= t0) & (rolls < t1)
        pressure[m] = rng.uniform(0.001, 0.004, size=m.sum())
        m = (rolls >= t1) & (rolls < t2)
        pressure[m] = rng.uniform(0.0005, 0.003, size=m.sum())
        m = (rolls >= t2) & (rolls < t3)
        pressure[m] = -rng.uniform(0.0005, 0.002, size=m.sum())

        if in_scn:
            net = pressure.mean(axis=1) * scn_scale - scn_bias
            shock = noise_all[d - 1] * scenario.vol_mult
        else:
            net = pressure.mean(axis=1) - drift_bias
            shock = noise_all[d - 1]
        paths[:, d] = paths[:, d - 1] * np.maximum(1 + net + shock, 0.01)
        if d in divs:
            paths[:, d] = np.maximum(paths[:, d] - divs[d], paths[:, d] * 0.01)

    finals = paths[:, -1]
    start = current_price

    def pct(p: float) -> float:
        return round(float(np.percentile(finals, p)), 2)

    bands = {"p10": pct(10), "p25": pct(25), "p50": pct(50), "p75": pct(75), "p90": pct(90)}
    prob_up = round(float((finals > start).mean()), 3)

    q = np.percentile(paths, [10, 25, 50, 75, 90], axis=0)
    daily_bands = {k: [round(float(v), 2) for v in row] for k, row in zip(("p10", "p25", "p50", "p75", "p90"), q)}

    sample_idx = rng.choice(runs, size=min(sample_count, runs), replace=False)
    sample_paths = [[round(float(v), 2) for v in paths[i]] for i in sample_idx]

    shown_mix = mix.as_dict()
    if scenario is not None:
        s = scn_shares
        shown_mix = AgentMix(*[float(x) for x in s], passive_holders=float(max(0.0, 1 - s.sum()))).as_dict()

    return {
        "current_price": round(float(start), 2),
        "horizon_days": days,
        "runs": runs,
        "agents": agents,
        "daily_vol": round(vol * (scenario.vol_mult if scenario else 1.0), 5),
        "vol_method": vol_method or ("default" if daily_vol is None else "given"),
        "drift_scale": float(drift_scale),
        "scenario": scenario.id if scenario else None,
        "events": [{"day": d, "type": "dividend", "amount": round(a, 2)} for d, a in sorted(divs.items())],
        "agent_mix": shown_mix,
        "bands": bands,
        "daily_bands": daily_bands,
        "expected_return_pct": round((bands["p50"] / start - 1) * 100, 2),
        "prob_price_up": prob_up,
        "sample_paths": sample_paths,
    }
