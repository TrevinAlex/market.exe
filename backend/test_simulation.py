import asyncio
from datetime import date

import numpy as np
from fastapi.testclient import TestClient

import app.main as main
from app.core.simulation import (
    MAX_DAILY_VOL, MIN_DAILY_VOL, predict_daily_vol, run_simulation, upcoming_dividends,
)

GOOD = {"momentum": 1.0, "debt": 1.0, "valuation": 1.0, "quality": 1.0, "profitability": 1.0}

rng = np.random.default_rng(0)
calm = list(6000 * np.exp(np.cumsum(rng.normal(0, 0.01, 60))))
wild = list(6000 * np.exp(np.cumsum(rng.normal(0, 0.04, 60))))
v_calm, m1 = predict_daily_vol(calm, 7000, 5500)
v_wild, m2 = predict_daily_vol(wild, 7000, 5500)
assert m1 == m2 == "ml" and v_wild > v_calm, (v_calm, v_wild)
assert MIN_DAILY_VOL <= v_calm <= MAX_DAILY_VOL
v, m = predict_daily_vol(calm[:10], 7000, 5500)
assert m == "range" and v > 0
assert predict_daily_vol(None, None, None) == (None, "default")

base = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015)
biased = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, drift_scale=1.0)
assert abs(base["bands"]["p50"] / 1000 - 1) < 0.01, base["bands"]
assert biased["bands"]["p50"] > base["bands"]["p50"] * 1.03, (biased["bands"], base["bands"])
assert 0.45 < base["prob_price_up"] < 0.55

div = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, dividends=[(10, 50)])
shift = base["bands"]["p50"] - div["bands"]["p50"]
assert 40 < shift < 60, shift
assert div["events"] == [{"day": 10, "type": "dividend", "amount": 50.0}]
assert run_simulation(1000, GOOD, runs=50, seed=1, dividends=[(31, 50), (5, 0)])["events"] == []

w = lambda s: s["bands"]["p90"] - s["bands"]["p10"]
herd = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, herding=8)
contra = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, contrarian=8)
assert w(herd) > w(base) * 1.03 > w(base) > w(contra) * 1.01, (w(herd), w(base), w(contra))

db = base["daily_bands"]
assert all(len(db[k]) == 31 for k in ("p10", "p25", "p50", "p75", "p90"))
assert db["p10"][0] == db["p90"][0] == 1000
assert all(db["p10"][d] <= db["p50"][d] <= db["p90"][d] for d in range(31))
assert db["p90"][30] == base["bands"]["p90"] and db["p10"][30] == base["bands"]["p10"]

from app.core.scoring import score_company
bd = score_company({"symbol": "X", "roe_ttm": 0.18, "pe_ttm": None}).breakdown
assert bd["quality"]["input"] == "ROE 18.0%" and "25%" in bd["quality"]["rule"]
assert bd["valuation"]["input"] is None and bd["momentum"]["input"] is None

today = date(2026, 10, 5)
ca = {
    "upcoming_dividend": {"ex_date": "2026-10-09", "dividend_amount": 55},
    "dividend": [
        {"ex_date": "2026-10-09", "dividend_amount": 55},
        {"ex_date": "2025-12-03", "dividend_amount": 40},
        {"ex_date": "2027-03-01", "dividend_amount": 60},
        {"ex_date": "bad", "dividend_amount": 1},
    ],
}
assert upcoming_dividends(ca, 30, today) == [(5, 55.0)], upcoming_dividends(ca, 30, today)
assert upcoming_dividends(None, 30, today) == []
assert upcoming_dividends({"upcoming_dividend": None, "dividend": None}, 30, today) == []

REPORT = {"symbol": "BBCA.JK", "company_name": "Bank Central Asia",
          "overview": {"last_close_price": 6100, "52_w_high": {"d": 10000}, "52_w_low": {"d": 7000}},
          "valuation": {"forward_pe": 15},
          "financials": {"historical_financial_ratio": [{"profitability": {"roe": .2, "roa": .03},
                                                          "leverage": {"debt_to_equity_ratio": .1}}]}}


async def report(sym):
    return REPORT


async def closes_ok(sym):
    return [{"date": f"d{i:03d}", "close": c, "volume": 2_000_000} for i, c in enumerate(calm)]


async def actions_ok(sym):
    return {"upcoming_dividend": {"ex_date": date.today().replace(day=1).isoformat(), "dividend_amount": 55}}


async def boom(sym):
    raise RuntimeError("Sectors down")


main.sectors_client.company_report = report
client = TestClient(main.app)

main.sectors_client.daily_rows, main.sectors_client.corporate_actions = closes_ok, actions_ok
r = client.post("/api/simulate/BBCA?runs=200")
assert r.status_code == 200, r.text
assert r.json()["vol_method"] == "ml" and r.json()["drift_scale"] == 0.0
liq = r.json()["liquidity"]
assert liq["days"] == 20 and liq["avg_daily_volume"] == 2_000_000, liq
assert 2_000_000 * min(calm[-20:]) <= liq["avg_daily_value"] <= 2_000_000 * max(calm[-20:]), liq
ids = [s["id"] for s in r.json()["scenarios"]]
assert ids == ["panic_2020", "rally_2020"], ids
panic, rally = r.json()["scenarios"]
assert panic["bands"]["p50"] < r.json()["bands"]["p10"] < r.json()["bands"]["p90"] < rally["bands"]["p50"], r.json()
assert len(panic["sample_paths"]) == 12 and len(panic["daily_bands"]["p10"]) == 31

main.sectors_client.daily_rows, main.sectors_client.corporate_actions = boom, boom
r = client.post("/api/simulate/BBCA?runs=200")
assert r.status_code == 200, r.text
j = r.json()
assert j["vol_method"] == "range" and j["events"] == [] and j["liquidity"] is None, j

print("OK -- simulation: ML vol, drift removed, dividends applied and parsed, route fail-soft.")

from app.core.scoring import fundamentals_history

hist_report = {
    "financials": {"historical_financial_ratio": [
        {"year": "2021", "profitability": {"roe": .25, "roa": .15}, "leverage": {"debt_to_equity_ratio": 0}},
        {"year": "2022", "profitability": {"roe": .20, "roa": .10}, "leverage": {"debt_to_equity_ratio": .5}},
        {"year": "2023", "profitability": {"roe": .05, "roa": .02}, "leverage": {"debt_to_equity_ratio": 2.0}},
        {"year": "bad"},
    ]},
    "valuation": {"historical_valuation": [{"year": 2021, "pe": 5}, {"year": 2023, "pe": 30}]},
}
fh = fundamentals_history(hist_report)
assert [y["year"] for y in fh["years"]] == [2021, 2022, 2023], fh
assert fh["years"][0]["score"] == 100.0, fh["years"][0]
assert fh["years"][1]["pe"] is None and fh["years"][1]["valuation"] == 10.0
assert fh["trend"] == "deteriorating", fh
assert fundamentals_history({}) == {"years": [], "trend": None}

main.sectors_client.company_report = report
r = client.post("/api/simulate/BBCA?runs=200")
assert r.status_code == 200 and r.json()["fundamentals"] == [], r.text

print("OK -- fundamentals history: yearly scores, missing data neutral, trend, route field.")
