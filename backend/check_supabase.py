import asyncio
import uuid

import httpx

from app.config import settings
from app.services.history import HistoryStore
from app.services.pins import PinStore


async def main() -> None:
    url, key = settings.supabase_url, settings.supabase_service_key
    if not url or not key:
        print("[x] SUPABASE_URL / SUPABASE_SERVICE_KEY are empty in backend/.env")
        return
    if key.startswith("sb_publishable_"):
        print("[x] That is the PUBLISHABLE key. Use a SECRET key (sb_secret_...).")
        return
    print(f"URL: {url}\nKey: {key[:12]}...{key[-4:]}")

    store = HistoryStore(url, key)
    probe = str(uuid.uuid4())
    try:
        async with store._client() as c:
            r = await c.post(store._base, json={
                "user_uid": probe, "kind": "company", "symbol": "TEST",
                "params": {}, "result": {"check": True},
            }, headers={"Prefer": "return=minimal"})
            if r.status_code >= 400:
                print(f"[x] Insert failed: HTTP {r.status_code} {r.text}")
                if "user_history" in r.text and ("does not exist" in r.text or "PGRST205" in r.text):
                    print("    -> Table missing. Run backend/supabase/schema.sql in the SQL Editor.")
                elif r.status_code in (401, 403):
                    print("    -> Key rejected. Check you copied the full secret key.")
                return
        rows, total = await store.list(probe)
        print(f"[ok] insert + read back: {total} row")
        print(f"[ok] cleanup: deleted {await store.delete(probe)} row")

        pins = PinStore(url, key)
        try:
            await pins.add(probe, "TEST")
            ok = [p["symbol"] for p in await pins.list(probe)] == ["TEST"]
            await pins.remove(probe, "TEST")
            print(f"[{'ok' if ok else 'x'}] user_pins table: pin + unpin")
        except httpx.HTTPStatusError as e:
            print(f"[x] user_pins: HTTP {e.response.status_code} {e.response.text}")
            print("    -> Re-run backend/supabase/schema.sql in the SQL Editor (it is safe to re-run).")
            return
        print("Supabase is ready. Restart the backend so it picks up .env.")
    except httpx.HTTPError as e:
        print(f"[x] Could not reach Supabase: {e}")


asyncio.run(main())
