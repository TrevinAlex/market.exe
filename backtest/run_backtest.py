"""Reproduce the MARKET.EXE model report card.

Walk-forward backtest of the price simulator against real IDX prices:

* Data: free daily closes + dividends from Yahoo Finance (no Sectors credits).
  Downloads are cached in backtest/data/ so a re-run works offline.
* Every 5 trading days, for every stock, start a 30-trading-day forecast using
  only prices known on that day, then compare it with the real price 30 days on.
* The volatility model (same features as app.core.simulation.predict_daily_vol)
  is re-fitted each test year on earlier data only, with a 45-day gap, so no
  forecast ever sees its own future.
* Each forecast runs the app's real ``run_simulation`` (drift off, dividends on).

Usage (from the repo root):
    backend\\.venv\\Scripts\\python.exe backtest\\run_backtest.py
    backend\\.venv\\Scripts\\python.exe backtest\\run_backtest.py --quick
Writes backtest/results.json and prints a summary table.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.core.simulation import (  # noqa: E402  (path set above)
    DEFAULT_DAILY_VOL,
    MAX_DAILY_VOL,
    MIN_DAILY_VOL,
    estimate_daily_vol,
    run_simulation,
)

# LQ45 constituents (2025/26). Younger listings simply contribute fewer forecasts.
TICKERS = [
    "ACES", "ADMR", "ADRO", "AKRA", "AMMN", "AMRT", "ANTM", "ARTO", "ASII", "BBCA",
    "BBNI", "BBRI", "BBTN", "BMRI", "BRIS", "BRPT", "CPIN", "CTRA", "ESSA", "EXCL",
    "GOTO", "ICBP", "INCO", "INDF", "INKP", "INTP", "ISAT", "ITMG", "JPFA", "JSMR",
    "KLBF", "MAPA", "MAPI", "MBMA", "MDKA", "MEDC", "PGAS", "PGEO", "PTBA", "SIDO",
    "SMGR", "TLKM", "TOWR", "UNTR", "UNVR",
]
QUICK_TICKERS = ["BBCA", "BBRI", "TLKM", "ASII", "ANTM", "ADRO", "BRPT", "UNVR"]

HORIZON = 30          # trading days forecast ahead
STEP = 5              # trading days between forecast start dates
LOOKBACK = 252        # one year of closes, for the 52-week range
GAP_DAYS = 45         # calendar-day gap between training data and the test year
FIRST_TEST_YEAR = 2019
NEUTRAL = {k: 0.5 for k in ("valuation", "momentum", "debt", "quality", "profitability")}

DATA = HERE / "data"


# --------------------------------------------------------------------------- data
def fetch(symbol: str, start: date, end: date) -> dict:
    """Daily closes + dividends for SYMBOL.JK, cached as JSON."""
    DATA.mkdir(exist_ok=True)
    cache = DATA / f"{symbol}_{start}_{end}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(end.year, end.month, end.day, tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.JK"
           f"?period1={p1}&period2={p2}&interval=1d&events=div")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.load(resp)["chart"]["result"][0]
    offset = res["meta"].get("gmtoffset", 25200)
    to_day = lambda ts: (datetime.fromtimestamp(ts + offset, tz=timezone.utc)).date().isoformat()  # noqa: E731
    closes = res["indicators"]["quote"][0]["close"]
    rows = [(to_day(ts), c) for ts, c in zip(res.get("timestamp") or [], closes) if c]
    divs = [(to_day(int(ts)), float(v["amount"]))
            for ts, v in ((res.get("events") or {}).get("dividends") or {}).items()]
    out = {"dates": [d for d, _ in rows], "closes": [float(c) for _, c in rows], "dividends": sorted(divs)}
    cache.write_text(json.dumps(out))
    time.sleep(0.3)  # be polite to the free endpoint
    return out


# ----------------------------------------------------------------------- samples
def build_samples(symbol: str, raw: dict) -> list[dict]:
    """One forecast start every STEP days, with features known on that day only."""
    dates = [date.fromisoformat(d) for d in raw["dates"]]
    c = np.array(raw["closes"], dtype=float)
    n = len(c)
    # map each dividend's ex-date to the first trading day on/after it
    div_at: dict[int, float] = {}
    for d, amt in raw["dividends"]:
        idx = int(np.searchsorted(np.array(raw["dates"]), d))
        if idx < n and amt > 0:
            div_at[idx] = div_at.get(idx, 0.0) + amt

    samples = []
    for t in range(LOOKBACK, n - HORIZON, STEP):
        window = c[t - LOOKBACK + 1: t + 1]
        r60 = np.diff(np.log(c[t - 60: t + 1]))
        v5, v20, v60 = (float(np.std(r60[-k:])) for k in (5, 20, 60))
        v_range = estimate_daily_vol(window.max(), window.min())
        future = np.diff(np.log(c[t: t + HORIZON + 1]))
        realized = float(np.std(future))
        if v_range is None or min(v5, v20, v60, realized) <= 0:
            continue  # suspended / flat stretches carry no volatility information
        r20 = abs(float(np.log(c[t] / c[t - 20])))
        samples.append({
            "symbol": symbol,
            "start": dates[t],
            "end": dates[t + HORIZON],
            "price": float(c[t]),
            "actual": float(c[t + HORIZON]),
            "x": [1.0, np.log(v_range), np.log(v5), np.log(v20), np.log(v60), np.log(r20 + 0.01)],
            "v_range": v_range,
            "realized": realized,
            "divs": [(k - t, a) for k, a in div_at.items() if t < k <= t + HORIZON],
        })
    return samples


# ------------------------------------------------------------------- simulation
def simulate(s: dict, vol: float, seed: int, runs: int, agents: int, dividends: bool = True) -> dict:
    sim = run_simulation(s["price"], NEUTRAL, runs=runs, days=HORIZON, agents=agents, seed=seed,
                         daily_vol=vol, dividends=s["divs"] if dividends else None)
    return {**sim["bands"], "prob_up": sim["prob_price_up"]}


def coverage(rows: list[dict], key: str) -> dict:
    a = np.array([r["actual"] for r in rows])
    b = {p: np.array([r[key][p] for r in rows]) for p in ("p10", "p25", "p50", "p75", "p90")}
    return {
        "n": len(rows),
        "inside_p10_p90": float(np.mean((a >= b["p10"]) & (a <= b["p90"]))),
        "inside_p25_p75": float(np.mean((a >= b["p25"]) & (a <= b["p75"]))),
        "below_p10": float(np.mean(a < b["p10"])),
        "above_p90": float(np.mean(a > b["p90"])),
        "median_width_p10_p90_pct": float(np.median((b["p90"] - b["p10"]) / np.array([r["price"] for r in rows])) * 100),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true", help="8 stocks, fewer runs (about a minute)")
    ap.add_argument("--baselines", action="store_true", help="also simulate the 52-week-range-only and fixed 0.8%% vol versions")
    ap.add_argument("--start", default="2016-01-01")
    ap.add_argument("--end", default="2026-10-01", help="fixed end date so results are reproducible")
    ap.add_argument("--runs", type=int, default=400, help="simulated runs per forecast")
    ap.add_argument("--agents", type=int, default=100,
                    help="agents per run (drift is off, so agent count barely changes the bands; the app uses 1000)")
    args = ap.parse_args()
    if args.quick:
        args.runs = min(args.runs, 200)
    tickers = QUICK_TICKERS if args.quick else TICKERS
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)

    t0 = time.time()
    samples: list[dict] = []
    for sym in tickers:
        try:
            samples += build_samples(sym, fetch(sym, start, end))
        except Exception as exc:  # one bad ticker shouldn't stop the run
            print(f"  ! skipped {sym}: {exc}")
    print(f"{len(samples)} candidate forecasts from {len(tickers)} stocks ({time.time() - t0:.0f}s)")

    X = np.array([s["x"] for s in samples])
    y = np.log([s["realized"] for s in samples])
    years = sorted({s["start"].year for s in samples if s["start"].year >= FIRST_TEST_YEAR})

    tested: list[dict] = []
    per_year = {}
    for yr in years:
        cutoff = date(yr, 1, 1) - timedelta(days=GAP_DAYS)
        train = np.array([s["end"] < cutoff for s in samples])
        test_idx = [i for i, s in enumerate(samples) if s["start"].year == yr]
        if train.sum() < 200 or not test_idx:
            continue
        beta, *_ = np.linalg.lstsq(X[train], y[train], rcond=None)
        rows = []
        for i in test_idx:
            s = samples[i]
            vol = float(np.clip(np.exp(X[i] @ beta), MIN_DAILY_VOL, MAX_DAILY_VOL))
            row = {**s, "vol_ml": vol, "ml": simulate(s, vol, i, args.runs, args.agents)}
            if s["divs"]:
                row["ml_nodiv"] = simulate(s, vol, i, args.runs, args.agents, dividends=False)
            if args.baselines:
                row["range"] = simulate(s, s["v_range"], i, args.runs, args.agents)
                row["fixed"] = simulate(s, DEFAULT_DAILY_VOL, i, args.runs, args.agents)
            rows.append(row)
        per_year[yr] = {**coverage(rows, "ml"), "train_n": int(train.sum())}
        tested += rows
        print(f"  {yr}: {len(rows):5d} forecasts  inside P10-P90 {per_year[yr]['inside_p10_p90']:.1%}"
              f"  ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- metrics
    a = np.array([r["actual"] for r in tested])
    p0 = np.array([r["price"] for r in tested])
    log_real = np.log([r["realized"] for r in tested])
    up_pred = np.array([r["ml"]["prob_up"] >= 0.5 for r in tested])
    up_real = a > p0
    div_rows = [r for r in tested if r["divs"]]

    def bias(rows, key):  # average (forecast median / real price - 1)
        return float(np.mean([r[key]["p50"] / r["actual"] - 1 for r in rows])) if rows else None

    results = {
        "settings": {"stocks": len(tickers), "horizon_days": HORIZON, "step_days": STEP, "runs": args.runs,
                     "agents": args.agents, "data_from": args.start, "data_to": args.end,
                     "test_years": [min(per_year), max(per_year)] if per_year else None},
        "forecasts": len(tested),
        "range_calibration": coverage(tested, "ml"),
        "volatility_correlation": {
            "ml_model": float(np.corrcoef(np.log([r["vol_ml"] for r in tested]), log_real)[0, 1]),
            "range_only": float(np.corrcoef(np.log([r["v_range"] for r in tested]), log_real)[0, 1]),
        },
        "dividends": {
            "windows_with_ex_date": len(div_rows),
            "median_bias_without_dividends": bias(div_rows, "ml_nodiv"),
            "median_bias_with_dividends": bias(div_rows, "ml"),
        },
        "direction": {
            "accuracy": float(np.mean(up_pred == up_real)),
            "share_of_windows_that_went_up": float(np.mean(up_real)),
        },
        "per_year": {str(k): v for k, v in per_year.items()},
    }
    if args.baselines:
        results["baselines"] = {"range_only": coverage(tested, "range"), "fixed_0.8pct": coverage(tested, "fixed")}

    out = HERE / ("results_quick.json" if args.quick else "results.json")
    out.write_text(json.dumps(results, indent=2))

    rc, vc, dv, di = (results[k] for k in ("range_calibration", "volatility_correlation", "dividends", "direction"))
    print("\n=== MARKET.EXE report card ===")
    print(f"forecasts tested            {results['forecasts']:,}")
    print(f"inside P10-P90 (target 80%) {rc['inside_p10_p90']:.1%}   below P10 {rc['below_p10']:.1%} / above P90 {rc['above_p90']:.1%}")
    print(f"inside P25-P75 (target 50%) {rc['inside_p25_p75']:.1%}")
    print(f"volatility correlation      ML {vc['ml_model']:.2f}  vs 52-week range only {vc['range_only']:.2f}")
    if dv["windows_with_ex_date"]:
        print(f"dividend windows ({dv['windows_with_ex_date']})      median too high by {dv['median_bias_without_dividends']:+.1%}"
              f" without dividends, {dv['median_bias_with_dividends']:+.1%} with")
    print(f"direction accuracy          {di['accuracy']:.1%}  (share of windows that went up: {di['share_of_windows_that_went_up']:.1%})")
    if args.baselines:
        for k, v in results["baselines"].items():
            print(f"baseline {k:<18} inside P10-P90 {v['inside_p10_p90']:.1%}")
    print(f"\nwrote {out.relative_to(HERE.parent)} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
