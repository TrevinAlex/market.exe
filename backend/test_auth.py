import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_tmp, "auth_test.db")
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["LOGIN_MAX_FAILURES"] = "3"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"

from fastapi.testclient import TestClient

from app.main import app

c = TestClient(app)

assert c.get("/api/company/BB!!").status_code == 400
for path in ("/", "/health", "/docs", "/openapi.json"):
    assert c.get(path).status_code == 200, f"{path} should be public"
assert "admin" not in c.get("/").json()
assert c.post("/api/admin/login", json={"password": "anything"}).status_code == 404

creds = {"username": "guarduser", "password": "right-pass-1"}
assert c.post("/api/auth/register", json=creds).status_code == 201
for _ in range(3):
    assert c.post("/api/auth/login", json={**creds, "password": "wrong-pass-1"}).status_code == 401
r = c.post("/api/auth/login", json=creds)
assert r.status_code == 429 and "Retry-After" in r.headers, r.status_code

print("OK -- auth: viewing public, no admin login, brute-force guard trips.")
