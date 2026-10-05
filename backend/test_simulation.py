"""Offline tests for the simulation upgrades (no API key, no credits).

Run: .venv\\Scripts\\python.exe test_simulation.py
"""
import asyncio
from datetime import date

import numpy as np
from fastapi.testclient import TestClient

import app.main as main
from app.core.simulation import (
    MAX_DAILY_VOL, MIN_DAILY_VOL, predict_daily_vol, run_simulation, upcoming_dividends,
)

GOOD = {"momentum": 1.0, "debt": 1.0, "valuation": 1.0, "quality": 1.0, "profitability": 1.0}

# 1. Volatility model: ml with enough closes, range without, default with nothing.
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

# 2. Drift removed by default: strong scores no longer push the median up.
base = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015)
biased = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, drift_scale=1.0)
assert abs(base["bands"]["p50"] / 1000 - 1) < 0.01, base["bands"]
assert biased["bands"]["p50"] > base["bands"]["p50"] * 1.03, (biased["bands"], base["bands"])
assert 0.45 < base["prob_price_up"] < 0.55

# 3. A known dividend lowers the whole distribution by about its amount.
div = run_simulation(1000, GOOD, runs=2000, seed=1, daily_vol=0.015, dividends=[(10, 50)])
shift = base["bands"]["p50"] - div["bands"]["p50"]
assert 40 < shift < 60, shift
assert div["events"] == [{"day": 10, "type": "dividend", "amount": 50.0}]
# outside the horizon / bad values are ignored
assert run_simulation(1000, GOOD, runs=50, seed=1, dividends=[(31, 50), (5, 0)])["events"] == []

# 4. Parsing Sectors corporate actions.
today = date(2026, 10, 5)  # a Monday
ca = {
    "upcoming_dividend": {"ex_date": "2026-10-09", "dividend_amount": 55},
    "dividend": [
        {"ex_date": "2026-10-09", "dividend_amount": 55},   # duplicate of upcoming
        {"ex_date": "2025-12-03", "dividend_amount": 40},   # past
        {"ex_date": "2027-03-01", "dividend_amount": 60},   # beyond 30 trading days
        {"ex_date": "bad", "dividend_amount": 1},
    ],
}
assert upcoming_dividends(ca, 30, today) == [(5, 55.0)], upcoming_dividends(ca, 30, today)
assert upcoming_dividends(None, 30, today) == []
assert upcoming_dividends({"upcoming_dividend": None, "dividend": None}, 30, today) == []

# 5. Route: uses all three sources, and survives when the extra two fail.
REPORT = {"symbol": "BBCA.JK", "company_name": "Bank Central Asia",
          "overview": {"last_close_price": 6100, "52_w_high": {"d": 10000}, "52_w_low": {"d": 7000}},
          "valuation": {"forward_pe": 15},
          "financials": {"historical_financial_ratio": [{"profitability": {"roe": .2, "roa": .03},
                                                          "leverage": {"debt_to_equity_ratio": .1}}]}}


async def report(sym):
    return REPORT


async def closes_ok(sym):
    return calm


async def actions_ok(sym):
    return {"upcoming_dividend": {"ex_date": date.today().replace(day=1).isoformat(), "dividend_amount": 55}}


async def boom(sym):
    raise RuntimeError("Sectors down")


main.sectors_client.company_report = report
client = TestClient(main.app)

main.sectors_client.daily_closes, main.sectors_client.corporate_actions = closes_ok, actions_ok
r = client.post("/api/simulate/BBCA?runs=200")
assert r.status_code == 200, r.text
assert r.json()["vol_method"] == "ml" and r.json()["drift_scale"] == 0.0

main.sectors_client.daily_closes, main.sectors_client.corporate_actions = boom, boom
r = client.post("/api/simulate/BBCA?runs=200")
assert r.status_code == 200, r.text
j = r.json()
assert j["vol_method"] == "range" and j["events"] == [], j

print("OK -- simulation: ML vol, drift removed, dividends applied and parsed, route fail-soft.")
