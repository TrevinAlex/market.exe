"""Which long-run volatility input fixes the 'pulled toward the average' problem?

calibration_breakdown.py showed the volatility model is too wide for calm large
caps (BBCA 90% inside the 80% band) and too narrow for miners (BRPT 66%).
This compares volatility-model variants walk-forward (refit each year on
earlier data, 45-day gap), using closed-form bands so every variant is scored
on identical forecasts in seconds instead of re-running the full simulation:

    band_q = (price - dividends in window) * exp(z_q * vol * sqrt(30))

That is what run_simulation produces with drift off; the baseline here should
land close to run_backtest.py's simulated 79.5%.

Variants (all keep the app's current six inputs):
    current      the app's model today
    +sector      IDX-IC sector of the stock (free: it's in the company report)
    +vol250      realised vol over the last 250 trading days (needs ~1 year
                 of daily closes = 4 calls to the 90-day Sectors endpoint)
    +both        sector and vol250
    stock-FE     a separate intercept per stock -- an upper bound only, can't
                 be used for stocks outside the training set

Usage: backend/.venv/Scripts/python.exe backtest/vol_experiment.py
Uses the cached prices in backtest/data/ (no downloads, no Sectors credits).
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "backend"))
from run_backtest import (  # noqa: E402
    FIRST_TEST_YEAR, GAP_DAYS, HORIZON, LOOKBACK, STEP, TICKERS, fetch,
)
from app.core.simulation import MAX_DAILY_VOL, MIN_DAILY_VOL, estimate_daily_vol  # noqa: E402

# IDX-IC sector as the Sectors company report names it (overview.sector).
IDXIC = {
    **dict.fromkeys(["BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS", "ARTO"], "Financials"),
    **dict.fromkeys(["ADRO", "ADMR", "AKRA", "ITMG", "MEDC", "PGAS", "PTBA"], "Energy"),
    **dict.fromkeys(["AMMN", "ANTM", "BRPT", "ESSA", "INCO", "INKP", "INTP", "MBMA", "MDKA", "SMGR"],
                    "Basic Materials"),
    **dict.fromkeys(["AMRT", "CPIN", "ICBP", "INDF", "JPFA", "UNVR"], "Consumer Non-Cyclicals"),
    **dict.fromkeys(["ACES", "MAPA", "MAPI"], "Consumer Cyclicals"),
    **dict.fromkeys(["KLBF", "SIDO"], "Healthcare"),
    **dict.fromkeys(["EXCL", "ISAT", "JSMR", "PGEO", "TLKM", "TOWR"], "Infrastructures"),
    **dict.fromkeys(["ASII", "UNTR"], "Industrials"),
    "CTRA": "Properties & Real Estate",
    "GOTO": "Technology",
}
SECTORS = sorted(set(IDXIC.values()))
QS = np.array([0.10, 0.25, 0.50, 0.75, 0.90])
Z = np.array([-1.2815516, -0.6744898, 0.0, 0.6744898, 1.2815516])


def samples_for(sym: str) -> list[dict]:
    raw = fetch(sym, date(2016, 1, 1), date(2026, 10, 1))
    dates = [date.fromisoformat(d) for d in raw["dates"]]
    c = np.array(raw["closes"], dtype=float)
    n = len(c)
    div_at: dict[int, float] = {}
    for d, amt in raw["dividends"]:
        idx = int(np.searchsorted(np.array(raw["dates"]), d))
        if idx < n and amt > 0:
            div_at[idx] = div_at.get(idx, 0.0) + amt
    out = []
    for t in range(LOOKBACK, n - HORIZON, STEP):
        window = c[t - LOOKBACK + 1: t + 1]
        r60 = np.diff(np.log(c[t - 60: t + 1]))
        v5, v20, v60 = (float(np.std(r60[-k:])) for k in (5, 20, 60))
        v250 = float(np.std(np.diff(np.log(c[t - 250: t + 1]))))
        v_range = estimate_daily_vol(window.max(), window.min())
        realized = float(np.std(np.diff(np.log(c[t: t + HORIZON + 1]))))
        if v_range is None or min(v5, v20, v60, v250, realized) <= 0:
            continue
        r20 = abs(float(np.log(c[t] / c[t - 20])))
        out.append({
            "symbol": sym, "start": dates[t], "end": dates[t + HORIZON],
            "price": float(c[t]), "actual": float(c[t + HORIZON]),
            "div": sum(a for k, a in div_at.items() if t < k <= t + HORIZON),
            "base": [1.0, np.log(v_range), np.log(v5), np.log(v20), np.log(v60), np.log(r20 + 0.01)],
            "lv250": np.log(v250),
            "realized": realized,
        })
    return out


def design(rows: list[dict], variant: str) -> np.ndarray:
    X = [list(r["base"]) for r in rows]
    if variant in ("+sector", "+both"):
        for x, r in zip(X, rows):
            # Financials is the reference sector (largest group).
            x += [1.0 if IDXIC[r["symbol"]] == s else 0.0 for s in SECTORS if s != "Financials"]
    if variant in ("+vol250", "+both"):
        for x, r in zip(X, rows):
            x.append(r["lv250"])
    if variant == "stock-FE":
        for x, r in zip(X, rows):
            x += [1.0 if r["symbol"] == s else 0.0 for s in TICKERS[1:]]
    return np.array(X)


def score(rows: list[dict], vol: np.ndarray) -> dict:
    p = np.array([r["price"] for r in rows])
    a = np.array([r["actual"] for r in rows])
    d = np.array([r["div"] for r in rows])
    bands = (p - d)[:, None] * np.exp(np.outer(vol * np.sqrt(HORIZON), Z))
    inside80 = (a >= bands[:, 0]) & (a <= bands[:, 4])
    inside50 = (a >= bands[:, 1]) & (a <= bands[:, 3])
    err = (a[:, None] - bands) / p[:, None]
    pinball = float(np.mean(np.maximum(QS * err, (QS - 1) * err)))
    per_stock = {}
    for s in sorted({r["symbol"] for r in rows}):
        m = np.array([r["symbol"] == s for r in rows])
        if m.sum() >= 150:
            per_stock[s] = float(inside80[m].mean())
    per_sector = {}
    for s in SECTORS:
        m = np.array([IDXIC[r["symbol"]] == s for r in rows])
        if m.sum():
            per_sector[s] = float(inside80[m].mean())
    dev = np.abs(np.array(list(per_stock.values())) - 0.80)
    return {
        "inside_p10_p90": float(inside80.mean()),
        "inside_p25_p75": float(inside50.mean()),
        "pinball": pinball,
        "median_width_pct": float(np.median((bands[:, 4] - bands[:, 0]) / p) * 100),
        "per_stock_mean_abs_dev_pts": float(dev.mean() * 100),
        "stocks_off_by_5pts_or_more": int((dev >= 0.05).sum()),
        "worst_stocks": sorted(per_stock.items(), key=lambda kv: abs(kv[1] - 0.8), reverse=True)[:5],
        "per_sector": per_sector,
        "vol_corr": float(np.corrcoef(np.log(vol), np.log([r["realized"] for r in rows]))[0, 1]),
    }


def main() -> None:
    rows = [s for sym in TICKERS for s in samples_for(sym)]
    y = np.log([r["realized"] for r in rows])
    years = sorted({r["start"].year for r in rows if r["start"].year >= FIRST_TEST_YEAR})
    variants = ["current", "+sector", "+vol250", "+both", "stock-FE"]
    results, coefs = {}, {}
    for v in variants:
        X = design(rows, v)
        pred = np.full(len(rows), np.nan)
        for yr in years:
            cutoff = date(yr, 1, 1) - timedelta(days=GAP_DAYS)
            train = np.array([r["end"] < cutoff for r in rows])
            test = np.array([r["start"].year == yr for r in rows])
            beta, *_ = np.linalg.lstsq(X[train], y[train], rcond=None)
            pred[test] = np.clip(np.exp(X[test] @ beta), MIN_DAILY_VOL, MAX_DAILY_VOL)
        keep = ~np.isnan(pred)
        tested = [r for r, k in zip(rows, keep) if k]
        results[v] = score(tested, pred[keep])
        # Final fit on everything (what the app would ship).
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        coefs[v] = beta.tolist()

    n_test = int(sum(1 for r in rows if r["start"].year >= FIRST_TEST_YEAR))
    print(f"{n_test:,} walk-forward forecasts, closed-form bands\n")
    hdr = f"{'variant':<10}{'in 80%':>8}{'in 50%':>8}{'pinball':>10}{'width':>8}{'stock dev':>11}{'off>=5':>8}{'vol r':>7}"
    print(hdr)
    for v in variants:
        r = results[v]
        print(f"{v:<10}{r['inside_p10_p90']:>8.1%}{r['inside_p25_p75']:>8.1%}{r['pinball']:>10.5f}"
              f"{r['median_width_pct']:>7.1f}%{r['per_stock_mean_abs_dev_pts']:>9.1f}pt"
              f"{r['stocks_off_by_5pts_or_more']:>6}/{len(results[v]['worst_stocks']) and 41:<2}"
              f"{r['vol_corr']:>6.2f}")
    print("\ninside 80% band by sector:")
    print(f"  {'sector':<26}" + "".join(f"{v:>10}" for v in variants))
    for s in SECTORS:
        print(f"  {s:<26}" + "".join(f"{results[v]['per_sector'].get(s, float('nan')):>10.1%}" for v in variants))
    for v in variants:
        print(f"\nworst stocks, {v}: " + ", ".join(f"{s} {x:.0%}" for s, x in results[v]["worst_stocks"]))
    (HERE / "results_vol_experiment.json").write_text(json.dumps(
        {"results": results, "full_sample_coefficients": coefs, "sectors": SECTORS}, indent=2, default=str))
    print("\nwrote backtest/results_vol_experiment.json")


if __name__ == "__main__":
    main()
