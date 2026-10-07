import json
import os
import tempfile
from urllib.parse import parse_qsl

_tmp = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_tmp, "users_pins.db")
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"
KEY = "sb_secret_testkey"
os.environ["SUPABASE_URL"] = "https://fake.supabase.co/rest/v1/"
os.environ["SUPABASE_SERVICE_KEY"] = KEY

import httpx
from fastapi.testclient import TestClient

import app.main as main
from app.services.pins import PinStore

PINS: list[dict] = []
_clock = [0]


def _match(row, q):
    return all(str(row[c]) == q[c].removeprefix("eq.") for c in ("user_uid", "symbol") if c in q)


def fake(req: httpx.Request) -> httpx.Response:
    assert req.url.path == "/rest/v1/user_pins", req.url.path
    assert req.headers["apikey"] == KEY and "authorization" not in req.headers
    q = dict(parse_qsl(req.url.query.decode()))
    if req.method == "GET":
        rows = sorted((r for r in PINS if _match(r, q)), key=lambda r: r["created_at"])
        return httpx.Response(200, json=[{"symbol": r["symbol"], "created_at": r["created_at"]} for r in rows])
    if req.method == "POST":
        assert q["on_conflict"] == "user_uid,symbol"
        row = json.loads(req.content)
        if not any(_match(r, {k: f"eq.{v}" for k, v in row.items()}) for r in PINS):
            _clock[0] += 1
            PINS.append({**row, "created_at": f"2026-10-05T10:00:{_clock[0]:02d}+00:00"})
        return httpx.Response(201)
    if req.method == "DELETE":
        gone = [r for r in PINS if _match(r, q)]
        for r in gone:
            PINS.remove(r)
        return httpx.Response(200, json=[{"symbol": r["symbol"]} for r in gone])
    return httpx.Response(405)


main.pin_store = PinStore(main.settings.supabase_url, KEY, max_pins=3, transport=httpx.MockTransport(fake))

main.history_store = type("NoHistory", (), {"enabled": False, "record": None})()

async def _fake_report(symbol):
    if symbol == "GONE":
        return None
    return {
        "symbol": f"{symbol}.JK", "company_name": f"PT {symbol} Tbk.", "sector": "Financials",
        "last_close_price": 1000.0, "daily_close_change": 0.0, "pe_ttm": 15.0,
        "52_w_high_price": 1200.0, "52_w_low_price": 800.0, "der_mrq": 0.5,
        "roe_ttm": 0.15, "roa_ttm": 0.02,
    }


main.sectors_client.company_report = _fake_report
main.flatten_report = lambda r: r

c = TestClient(main.app)


def register(name):
    r = c.post("/api/auth/register", json={"username": name, "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


alice, bob = register("alice"), register("bob")

assert c.get("/api/pins").status_code == 401
assert c.put("/api/pins/BBCA").status_code == 401

assert c.put("/api/pins/bbca", headers=alice).json() == {"symbol": "BBCA", "pinned": True, "added": True}
assert c.put("/api/pins/BBCA.JK", headers=alice).json()["added"] is False
assert c.put("/api/pins/TLKM", headers=alice).status_code == 200
r = c.get("/api/pins", headers=alice).json()
assert [p["symbol"] for p in r["pins"]] == ["BBCA", "TLKM"] and r["max_pins"] == 3
assert all(p["score"] is None for p in r["pins"])

assert c.put("/api/pins/BB'1", headers=alice).status_code == 400

assert c.put("/api/pins/GONE", headers=alice).status_code == 200
assert c.put("/api/pins/ASII", headers=alice).status_code == 409

r = c.get("/api/pins?scores=true", headers=alice).json()
by = {p["symbol"]: p["score"] for p in r["pins"]}
assert by["BBCA"]["company_name"] == "PT BBCA Tbk." and by["TLKM"]["composite"] > 0
assert by["GONE"] is None

assert c.get("/api/pins", headers=bob).json()["pins"] == []
assert c.delete("/api/pins/BBCA", headers=bob).json()["removed"] is False
assert len(c.get("/api/pins", headers=alice).json()["pins"]) == 3

assert c.delete("/api/pins/BBCA", headers=alice).json() == {"symbol": "BBCA", "pinned": False, "removed": True}
assert c.delete("/api/pins/BBCA", headers=alice).json()["removed"] is False
assert [p["symbol"] for p in c.get("/api/pins", headers=alice).json()["pins"]] == ["TLKM", "GONE"]

main.pin_store = PinStore("https://x.supabase.co", KEY, transport=httpx.MockTransport(lambda r: httpx.Response(500)))
assert c.get("/api/pins", headers=alice).status_code == 502
main.pin_store = PinStore("", "")
assert c.get("/api/pins", headers=alice).status_code == 503

print("OK -- pins: auth, pin/unpin idempotent, ticker validation, limit, scores, isolation, error paths.")
