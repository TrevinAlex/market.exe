"""User history checks -- no Supabase project or Sectors credits needed.

Supabase's PostgREST API is replaced by an in-memory fake (httpx.MockTransport)
that implements just the filters HistoryStore uses.

Run from backend/:  .venv\\Scripts\\python.exe test_history.py
"""
import json
import os
import tempfile
from urllib.parse import parse_qsl

_tmp = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_tmp, "users_hist.db")
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"
os.environ["SUPABASE_URL"] = "https://fake.supabase.co"
KEY = "sb_secret_testkey"
os.environ["SUPABASE_SERVICE_KEY"] = KEY

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app.services.history import HistoryStore  # noqa: E402

ROWS: list[dict] = []
_next_id = [1]


def _match(row: dict, q: dict) -> bool:
    for col in ("user_uid", "kind", "id"):
        if col in q and str(row[col]) != q[col].removeprefix("eq."):
            return False
    return True


def fake_postgrest(req: httpx.Request) -> httpx.Response:
    assert req.url.path == "/rest/v1/user_history", req.url.path
    assert req.headers["apikey"] == KEY
    assert "authorization" not in req.headers
    q = dict(parse_qsl(req.url.query.decode()))
    if req.method == "POST":
        row = json.loads(req.content)
        row.update(id=_next_id[0], created_at=f"2026-10-05T09:00:{_next_id[0]:02d}+00:00")
        _next_id[0] += 1
        ROWS.append(row)
        return httpx.Response(201)
    if req.method == "GET":
        hits = sorted((r for r in ROWS if _match(r, q)), key=lambda r: r["id"], reverse=True)
        off, lim = int(q["offset"]), int(q["limit"])
        page = hits[off : off + lim]
        cols = q["select"].split(",")
        rng = f"{off}-{off + len(page) - 1}/{len(hits)}" if page else f"*/{len(hits)}"
        return httpx.Response(200, json=[{c: r[c] for c in cols} for r in page],
                              headers={"Content-Range": rng})
    if req.method == "DELETE":
        gone = [r for r in ROWS if _match(r, q)]
        for r in gone:
            ROWS.remove(r)
        return httpx.Response(200, json=[{"id": r["id"]} for r in gone])
    return httpx.Response(405)


main.history_store = HistoryStore(
    "https://fake.supabase.co", KEY, transport=httpx.MockTransport(fake_postgrest)
)

FAKE = {
    "symbol": "BBCA.JK", "company_name": "PT Bank Central Asia Tbk.", "sector": "Financials",
    "sub_sector": "Banks", "last_close_price": 9500.0, "daily_close_change": 0.004,
    "pe_ttm": 22.5, "52_w_high_price": 10800.0, "52_w_low_price": 8200.0,
    "der_mrq": 0.3, "roe_ttm": 0.21, "roa_ttm": 0.035,
}


async def _fake_report(symbol):
    return dict(FAKE)


main.sectors_client.company_report = _fake_report


async def _no_closes(symbol):
    return []


async def _no_actions(symbol):
    return {}


main.sectors_client.daily_rows = _no_closes
main.sectors_client.corporate_actions = _no_actions
main.flatten_report = lambda r: r

c = TestClient(main.app)


def register(name):
    r = c.post("/api/auth/register", json={"username": name, "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


alice, bob = register("alice"), register("bob")

assert c.get("/api/company/BBCA").status_code == 200
assert ROWS == []
assert c.get("/api/history").status_code == 401

assert c.get("/api/company/bbca", headers=alice).status_code == 200
assert c.post("/api/simulate/BBCA?runs=50&days=5", headers=alice).status_code == 200
assert c.get("/api/company/BBCA", headers=bob).status_code == 200
assert len(ROWS) == 3

r = c.get("/api/history", headers=alice)
assert r.status_code == 200, r.text
h = r.json()
assert h["total"] == 2
assert [e["kind"] for e in h["results"]] == ["simulation", "company"]
sim = h["results"][0]
assert sim["symbol"] == "BBCA" and sim["params"] == {"runs": 50, "days": 5}
assert {"expected_return_pct", "prob_price_up", "regime"} <= sim["result"].keys()

assert c.get("/api/history?kind=company", headers=alice).json()["total"] == 1
assert len(c.get("/api/history?limit=1", headers=alice).json()["results"]) == 1
assert c.get("/api/history?kind=bogus", headers=alice).status_code == 422

assert c.get("/api/history", headers=bob).json()["total"] == 1
alice_id = h["results"][0]["id"]
assert c.delete(f"/api/history/{alice_id}", headers=bob).status_code == 404
assert c.get("/api/history", headers=alice).json()["total"] == 2

assert c.delete(f"/api/history/{alice_id}", headers=alice).json() == {"deleted": 1}
assert c.delete("/api/history", headers=alice).json() == {"deleted": 1}
assert c.get("/api/history", headers=alice).json()["total"] == 0
assert c.get("/api/history", headers=bob).json()["total"] == 1

main.history_store = HistoryStore(
    "https://fake.supabase.co", KEY,
    transport=httpx.MockTransport(lambda req: httpx.Response(500)),
)
assert c.get("/api/company/BBCA", headers=alice).status_code == 200
assert c.get("/api/history", headers=alice).status_code == 502

main.history_store = HistoryStore("", "")
assert c.get("/api/history", headers=alice).status_code == 503

seen = {}


def _capture(req):
    seen.update(req.headers)
    return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})


main.history_store = HistoryStore("https://fake.supabase.co", "eyJlegacy", transport=httpx.MockTransport(_capture))
assert c.get("/api/history", headers=alice).status_code == 200
assert seen["apikey"] == "eyJlegacy" and seen["authorization"] == "Bearer eyJlegacy"

print("OK -- history: records only when logged in, newest-first, filter/paging, per-user isolation, delete, fail-soft.")
