"""Where is the simulator's range well calibrated, and where does it fail?

Splits the walk-forward forecasts from run_backtest.py by year, sector,
volatility level, market stress and dividend windows, and reports for each group
how often the real price landed inside P10-P90 (target 80%) and P25-P75
(target 50%), and on which side it missed.

Usage (from the repo root):
    backend/.venv/Scripts/python.exe backtest/run_backtest.py --dump backtest/data/forecasts.json
    backend/.venv/Scripts/python.exe backtest/calibration_breakdown.py backtest/data/forecasts.json
Writes backtest/results_breakdown.json.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

SECTOR = {
    **dict.fromkeys(["BBCA", "BBNI", "BBRI", "BBTN", "BMRI", "BRIS", "ARTO"], "Banks"),
    **dict.fromkeys(["ADRO", "ADMR", "ITMG", "PTBA", "MEDC", "ESSA", "PGAS", "AKRA"], "Energy"),
    **dict.fromkeys(["ANTM", "INCO", "MDKA", "MBMA", "AMMN", "BRPT", "INKP", "INTP", "SMGR"],
                    "Materials & mining"),
    **dict.fromkeys(["AMRT", "ICBP", "INDF", "UNVR", "CPIN", "JPFA", "SIDO", "KLBF"], "Consumer staples & health"),
    **dict.fromkeys(["ACES", "MAPA", "MAPI", "ASII"], "Consumer cyclicals"),
    **dict.fromkeys(["TLKM", "ISAT", "EXCL", "TOWR", "GOTO"], "Telecom & tech"),
    **dict.fromkeys(["CTRA", "JSMR", "UNTR", "PGEO"], "Property, infra & industrials"),
}

MIN_N = 150


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% interval for a proportion. Forecasts overlap in time, so the true
    uncertainty is wider than this -- treat it as a lower bound."""
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def stats(rows: list[dict]) -> dict:
    a = np.array([r["actual"] for r in rows])
    p = {k: np.array([r[k] for r in rows]) for k in ("p10", "p25", "p75", "p90")}
    inside80 = (a >= p["p10"]) & (a <= p["p90"])
    k = int(inside80.sum())
    lo, hi = wilson(k, len(rows))
    vol_ratio = np.array([r["realized"] / r["vol_ml"] for r in rows])
    return {
        "n": len(rows),
        "inside_p10_p90": float(inside80.mean()),
        "ci95": [lo, hi],
        "inside_p25_p75": float(((a >= p["p25"]) & (a <= p["p75"])).mean()),
        "below_p10": float((a < p["p10"]).mean()),
        "above_p90": float((a > p["p90"]).mean()),
        "realized_over_predicted_vol": float(np.median(vol_ratio)),
    }


def table(title: str, groups: dict[str, list[dict]]) -> dict:
    print(f"\n{title}")
    print(f"  {'group':<30}{'n':>6}{'in 80%':>9}{'95% CI':>15}{'in 50%':>8}{'<P10':>7}{'>P90':>7}{'vol x':>7}")
    out = {}
    for name, rows in groups.items():
        if not rows:
            continue
        s = stats(rows)
        out[name] = s
        flag = " *" if s["n"] < MIN_N else ""
        off = s["ci95"][1] < 0.80 or s["ci95"][0] > 0.80
        mark = "  <-- off" if off and s["n"] >= MIN_N else ""
        print(f"  {name:<30}{s['n']:>6}{s['inside_p10_p90']:>9.1%}"
              f"  {s['ci95'][0]:.0%}-{s['ci95'][1]:.0%}".ljust(15 + 2) +
              f"{s['inside_p25_p75']:>7.1%}{s['below_p10']:>7.1%}{s['above_p90']:>7.1%}"
              f"{s['realized_over_predicted_vol']:>7.2f}{flag}{mark}")
    return out


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "data" / "forecasts.json")
    rows = json.loads(path.read_text())
    for r in rows:
        r["year"] = r["start"][:4]
        r["sector"] = SECTOR.get(r["symbol"], "Other")

    vols = np.array([r["vol_ml"] for r in rows])
    edges = np.quantile(vols, [0.2, 0.4, 0.6, 0.8])
    names = ["1 calmest", "2", "3", "4", "5 most volatile"]
    for r in rows:
        r["vol_q"] = names[int(np.searchsorted(edges, r["vol_ml"]))]

    by_date = defaultdict(list)
    for r in rows:
        by_date[r["start"]].append(r["vol_ml"])
    mkt = {d: float(np.median(v)) for d, v in by_date.items()}
    m_edges = np.quantile(list(mkt.values()), [1 / 3, 2 / 3])
    m_names = ["calm market", "normal market", "stressed market"]
    for r in rows:
        r["mkt"] = m_names[int(np.searchsorted(m_edges, mkt[r["start"]]))]

    def group(key, order=None):
        g = defaultdict(list)
        for r in rows:
            g[r[key]].append(r)
        keys = order or sorted(g)
        return {k: g[k] for k in keys if k in g}

    print(f"{len(rows):,} forecasts. Target: 80% inside P10-P90, 50% inside P25-P75, 10% each side.")
    print("'vol x' = realized / predicted volatility (1.00 = right; >1 = range too narrow).")
    print("* = fewer than 150 forecasts. CIs ignore the overlap between forecasts, so they are optimistic.")
    out = {
        "overall": table("OVERALL", {"all": rows}),
        "by_year": table("BY YEAR", group("year")),
        "by_sector": table("BY SECTOR", group("sector")),
        "by_volatility_quintile": table("BY PREDICTED VOLATILITY", group("vol_q", names)),
        "by_market_state": table("BY MARKET STATE (median predicted vol that day)", group("mkt", m_names)),
        "by_dividend_window": table("DIVIDEND IN WINDOW", {
            "ex-dividend inside 30 days": [r for r in rows if r["has_div"]],
            "no dividend": [r for r in rows if not r["has_div"]],
        }),
        "by_stock": table("BY STOCK", group("symbol")),
    }
    (HERE / "results_breakdown.json").write_text(json.dumps(out, indent=2))
    print("\nwrote backtest/results_breakdown.json")


if __name__ == "__main__":
    main()
