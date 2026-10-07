"""Do price-reacting agents make the simulated ranges more accurate?

Today the agents ignore the price. This tests two kinds of reaction, each at
several strengths, against agents that ignore the price (the app's default):

    herding     falls recruit panic sellers, rises recruit momentum buyers
    contrarian  falls recruit value buyers, rises recruit profit takers

Same walk-forward setup as run_backtest.py (volatility model refitted each
year on earlier data with a 45-day gap; app's real run_simulation; dividends
on). Every variant uses the same seed per forecast, so the market noise is
identical and only the agents differ.

To avoid picking a winner by luck, strengths are chosen on 2019-2022 only and
then judged on 2023-2026, which played no part in the choice.

Usage: backend/.venv/Scripts/python.exe backtest/agent_experiment.py [RUNS] [YEAR]
(RUNS default 200; YEAR computes and caches one test year, so the ~20-minute
job can be split into short pieces.)
Uses the cached prices in backtest/data/ (no downloads, no Sectors credits).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "backend"))
from run_backtest import (  # noqa: E402
    FIRST_TEST_YEAR, GAP_DAYS, HORIZON, NEUTRAL, TICKERS, build_samples, fetch,
)
from app.core.simulation import MAX_DAILY_VOL, MIN_DAILY_VOL, run_simulation  # noqa: E402

TUNE_YEARS = range(2019, 2023)
HOLDOUT_YEARS = range(2023, 2027)
STRENGTHS = (0.5, 1, 2, 4, 8)
QS = np.array([0.10, 0.25, 0.50, 0.75, 0.90])
KEYS = ("p10", "p25", "p50", "p75", "p90")


def score(rows: list[dict], key: str) -> dict:
    p = np.array([r["price"] for r in rows])
    a = np.array([r["actual"] for r in rows])
    b = np.array([[r[key][k] for k in KEYS] for r in rows])
    err = (a[:, None] - b) / p[:, None]
    return {
        "n": len(rows),
        "pinball": float(np.mean(np.maximum(QS * err, (QS - 1) * err))),
        "inside_p10_p90": float(np.mean((a >= b[:, 0]) & (a <= b[:, 4]))),
        "inside_p25_p75": float(np.mean((a >= b[:, 1]) & (a <= b[:, 3]))),
        "below_p10": float(np.mean(a < b[:, 0])),
        "above_p90": float(np.mean(a > b[:, 4])),
        "median_width_pct": float(np.median((b[:, 4] - b[:, 0]) / p) * 100),
    }


def paired_se(rows: list[dict], key: str, base: str = "none") -> float:
    """Standard error of the pinball difference vs ``base`` (same forecasts)."""
    p = np.array([r["price"] for r in rows])
    a = np.array([r["actual"] for r in rows])

    def per_row(k):
        b = np.array([[r[k][q] for q in KEYS] for r in rows])
        err = (a[:, None] - b) / p[:, None]
        return np.mean(np.maximum(QS * err, (QS - 1) * err), axis=1)

    diff = per_row(key) - per_row(base)
    # forecasts overlap (5-day step, 30-day horizon): ~6x fewer independent ones
    return float(np.std(diff) / np.sqrt(len(diff) / 6))


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    only_year = int(sys.argv[2]) if len(sys.argv) > 2 else None  # compute one year, cache it, stop
    agents = 50
    variants = {"none": (0.0, 0.0)}
    variants.update({f"herd {s:g}": (float(s), 0.0) for s in STRENGTHS})
    variants.update({f"contra {s:g}": (0.0, float(s)) for s in STRENGTHS})

    t0 = time.time()
    samples = [s for sym in TICKERS for s in build_samples(sym, fetch(sym, date(2016, 1, 1), date(2026, 10, 1)))]
    X = np.array([s["x"] for s in samples])
    y = np.log([s["realized"] for s in samples])
    years = sorted({s["start"].year for s in samples if s["start"].year >= FIRST_TEST_YEAR})

    tested = []
    for yr in years:
        cache = HERE / "data" / f"agent_exp_{runs}r_{yr}.json"
        if cache.exists():
            tested += json.loads(cache.read_text())
            continue
        if only_year and yr != only_year:
            continue
        cutoff = date(yr, 1, 1) - timedelta(days=GAP_DAYS)
        train = np.array([s["end"] < cutoff for s in samples])
        beta, *_ = np.linalg.lstsq(X[train], y[train], rcond=None)
        rows = []
        for i, s in enumerate(samples):
            if s["start"].year != yr:
                continue
            vol = float(np.clip(np.exp(X[i] @ beta), MIN_DAILY_VOL, MAX_DAILY_VOL))
            row = {"symbol": s["symbol"], "year": yr, "price": s["price"], "actual": s["actual"]}
            for name, (h, c) in variants.items():
                sim = run_simulation(s["price"], NEUTRAL, runs=runs, days=HORIZON, agents=agents, seed=i,
                                     daily_vol=vol, dividends=s["divs"], herding=h, contrarian=c)
                row[name] = sim["bands"]
            rows.append(row)
        cache.write_text(json.dumps(rows))
        tested += rows
        print(f"  {yr} done ({time.time() - t0:.0f}s)", flush=True)
    if only_year or {r["year"] for r in tested} != set(years):
        print("not all years done yet; run again (finished years are cached)")
        return

    tune = [r for r in tested if r["year"] in TUNE_YEARS]
    hold = [r for r in tested if r["year"] in HOLDOUT_YEARS]
    crash = [r for r in tested if r["year"] == 2020]
    results = {}
    for name in variants:
        results[name] = {
            "tune": score(tune, name), "holdout": score(hold, name), "all": score(tested, name),
            "crash_2020_inside_p10_p90": score(crash, name)["inside_p10_p90"],
            "holdout_pinball_diff_se": paired_se(hold, name) if name != "none" else 0.0,
        }

    def best(prefix):
        names = [n for n in variants if n.startswith(prefix)]
        return min(names, key=lambda n: results[n]["tune"]["pinball"])

    picks = {"herding": best("herd"), "contrarian": best("contra")}
    base_hold = results["none"]["holdout"]["pinball"]
    verdict = {}
    for kind, name in picks.items():
        d = results[name]["holdout"]["pinball"] - base_hold
        verdict[kind] = {"picked_on_2019_2022": name, "holdout_pinball_change": d,
                         "holdout_change_pct": d / base_hold * 100,
                         "se": results[name]["holdout_pinball_diff_se"],
                         "better_on_holdout": d < 0}

    print(f"\n{len(tested):,} forecasts, {runs} runs x {agents} agents each\n")
    print(f"{'variant':<11}{'tune pinball':>13}{'holdout pinball':>17}{'hold in80':>10}{'hold in50':>10}"
          f"{'width':>8}{'2020 in80':>10}")
    for name in variants:
        r = results[name]
        print(f"{name:<11}{r['tune']['pinball']:>13.5f}{r['holdout']['pinball']:>17.5f}"
              f"{r['holdout']['inside_p10_p90']:>10.1%}{r['holdout']['inside_p25_p75']:>10.1%}"
              f"{r['all']['median_width_pct']:>7.1f}%{r['crash_2020_inside_p10_p90']:>10.1%}")
    print()
    for kind, v in verdict.items():
        print(f"{kind}: picked {v['picked_on_2019_2022']} on 2019-2022 -> holdout pinball "
              f"{v['holdout_change_pct']:+.2f}% (diff {v['holdout_pinball_change']:+.6f}, se {v['se']:.6f})")
    (HERE / "results_agent_experiment.json").write_text(json.dumps(
        {"settings": {"runs": runs, "agents": agents, "tune_years": [2019, 2022], "holdout_years": [2023, 2026]},
         "results": results, "verdict": verdict}, indent=2))
    print(f"\nwrote backtest/results_agent_experiment.json in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
