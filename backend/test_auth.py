"""Auth checks -- no Sectors API key or credits needed.

Run from backend/:  .venv\\Scripts\\python.exe test_auth.py
"""
import os

os.environ["APP_PASSWORD"] = "test-password-123"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["LOGIN_MAX_FAILURES"] = "3"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import issue_token, verify_token  # noqa: E402
from app.main import admin_only, app  # noqa: E402


@app.post("/api/admin/_test", dependencies=admin_only)
async def _admin_test() -> dict:
    return {"ok": True}


c = TestClient(app)
ADMIN = "/api/admin/_test"

assert c.get("/api/company/BB!!").status_code == 400
for path in ("/", "/health", "/docs", "/openapi.json"):
    assert c.get(path).status_code == 200, f"{path} should be public"

assert c.post(ADMIN).status_code == 401
assert c.post(ADMIN, headers={"Authorization": "Bearer nope"}).status_code == 401
good, _ = issue_token()
payload, sig = good.split(".")
tampered = payload[:-1] + ("A" if payload[-1] != "A" else "B") + "." + sig
assert not verify_token(tampered), "tampered token accepted"
assert not verify_token(issue_token(now=0)[0]), "expired token accepted"

assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
r = c.post("/api/admin/login", json={"password": "test-password-123"})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
r = c.post(ADMIN, headers={"Authorization": f"Bearer {token}"})
assert r.status_code == 200 and r.json() == {"ok": True}, r.status_code

for _ in range(3):
    c.post("/api/admin/login", json={"password": "wrong"})
r = c.post("/api/admin/login", json={"password": "test-password-123"})
assert r.status_code == 429 and "Retry-After" in r.headers, r.status_code

print("OK -- auth: viewing public, admin route locked, admin login works, brute-force guard trips.")
