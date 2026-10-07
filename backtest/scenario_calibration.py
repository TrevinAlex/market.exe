from __future__ import annotations

import itertools
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from app.core.simulation import Scenario, predict_daily_vol, run_simulation
from run_backtest import TICKERS

DATA = HERE / "data"
HORIZON = 30
NEUTRAL = {k: 0.5 for k in ("valuation", "momentum", "debt", "quality", "profitability")}
QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)

SHIFTS = {
    "panic": (0.25, -0.05, -0.04, 0.0),
    "rally": (-0.05, 0.25, 0.0, -0.04),
}


def load() -> dict[str, dict]:
    out = {}
    for sym in TICKERS:
        files = sorted(DATA.glob(f"{sym}_*.json"))
        if files:
            raw = json.loads(files[0].read_text())
            out[sym] = {
                "dates": np.array(raw["dates"]),
                "closes": np.array(raw["closes"], dtype=float),
                "dividends": raw["dividends"],
            }
    return out


def find_episodes(prices: dict[str, dict]) -> dict[str, str]:
    all_dates = sorted(set().union(*(set(p["dates"]) for p in prices.values())))
    all_dates = [d for d in all_dates if d >= "2017-01-01"]
    med = {}
    for i in range(0, len(all_dates) - HORIZON, 1):
        d0, d1 = all_dates[i], all_dates[i + HORIZON]
        rets = []
        for p in prices.values():
            i0, i1 = np.searchsorted(p["dates"], d0), np.searchsorted(p["dates"], d1)
            if i0 >= 260 and i1 < len(p["dates"]) and p["dates"][i0] == d0 and p["dates"][i1] == d1:
                rets.append(np.log(p["closes"][i1] / p["closes"][i0]))
        if len(rets) >= 30:
            med[d0] = float(np.median(rets))
    return {"panic": min(med, key=med.get), "rally": max(med, key=med.get), "_median": med}


def samples_at(prices: dict[str, dict], start: str) -> list[dict]:
    out = []
    for sym, p in prices.items():
        t = int(np.searchsorted(p["dates"], start))
        if t < 260 or t + HORIZON >= len(p["dates"]) or p["dates"][t] != start:
            continue
        c = p["closes"]
        window = c[t - 251: t + 1]
        vol, _ = predict_daily_vol(list(c[t - 60: t + 1]), window.max(), window.min())
        if vol is None:
            continue
        divs = []
        for d, amt in p["dividends"]:
            k = int(np.searchsorted(p["dates"], d))
            if t < k <= t + HORIZON and amt > 0:
                divs.append((k - t, float(amt)))
        out.append({"symbol": sym, "price": float(c[t]), "actual": float(c[t + HORIZON]),
                    "vol": vol, "divs": divs})
    return out


def score(samples: list[dict], scn: Scenario | None, runs: int = 300, agents: int = 200) -> dict:
    loss, inside, below, above, sims = 0.0, 0, 0, 0, []
    for i, s in enumerate(samples):
        r = run_simulation(s["price"], NEUTRAL, runs=runs, days=HORIZON, agents=agents, seed=1000 + i,
                           daily_vol=s["vol"], dividends=s["divs"], scenario=scn, sample_count=1)
        b = r["bands"]
        y = s["actual"] / s["price"]
        for q, k in zip(QUANTILES, ("p10", "p25", "p50", "p75", "p90")):
            qv = b[k] / s["price"]
            loss += max(q * (y - qv), (q - 1) * (y - qv))
        inside += b["p10"] <= s["actual"] <= b["p90"]
        below += s["actual"] < b["p10"]
        above += s["actual"] > b["p90"]
        sims.append((b["p50"] / s["price"] - 1) * 100)
    n = len(samples)
    return {"pinball": loss / (n * len(QUANTILES)), "inside_p10_p90": inside / n,
            "below_p10": below / n, "above_p90": above / n,
            "sim_median_return_pct": float(np.median(sims))}


def fit(name: str, samples: list[dict], flat: bool = False) -> dict:
    sign = -1 if name == "panic" else 1
    base = Scenario(id=name, label=name, shift=SHIFTS[name], intensity=0.0, vol_mult=1.0, herding=0.0,
                    length=HORIZON, window="", description="", fit_inside_p10_p90=0, fit_n=0,
                    historical_median_return_pct=0, flat=flat)
    pushes = (0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.0175, 0.02, 0.025) if flat else \
        (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.2)
    grid = itertools.product(
        [sign * x for x in pushes],
        (1.0, 1.5, 2.0, 2.5, 3.0, 4.0),
        (0.0, 1.0, 2.0),
    )
    best = None
    for inten, vm, h in grid:
        res = score(samples, replace(base, intensity=inten, vol_mult=vm, herding=h))
        if best is None or res["pinball"] < best[1]["pinball"]:
            best = ((inten, vm, h), res)
    (inten, vm, h), res = best
    final = score(samples, replace(base, intensity=inten, vol_mult=vm, herding=h), runs=500, agents=1000)
    return {"intensity": inten, "vol_mult": vm, "herding": h, "flat": flat, **final}


def main() -> None:
    only = sys.argv[1:]
    prices = load()
    ep = find_episodes(prices)
    med = ep.pop("_median")
    ref = prices["BBCA"]
    out_file = HERE / "results_scenarios.json"
    report = json.loads(out_file.read_text()) if out_file.exists() else {}
    for name, start in ep.items():
        if only and name not in only:
            continue
        samples = samples_at(prices, start)
        actual = [(s["actual"] / s["price"] - 1) * 100 for s in samples]
        normal = score(samples, None, runs=500, agents=1000)
        fitted_vol = fit(name, samples, flat=False)
        fitted_flat = fit(name, samples, flat=True)
        fitted = min(fitted_vol, fitted_flat, key=lambda f: f["pinball"])
        report[name] = {
            "start": start,
            "end": str(ref["dates"][int(np.searchsorted(ref["dates"], start)) + HORIZON]),
            "n": len(samples),
            "median_stock_log_return": med[start],
            "actual_median_return_pct": float(np.median(actual)),
            "actual_p10_return_pct": float(np.percentile(actual, 10)),
            "actual_p90_return_pct": float(np.percentile(actual, 90)),
            "normal_model": normal,
            "fitted_vol_scaled": fitted_vol,
            "fitted_flat": fitted_flat,
            "fitted": fitted,
        }
        print(name, json.dumps(report[name], indent=1, default=str))
        out_file.write_text(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
