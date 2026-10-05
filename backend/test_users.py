"""User register/login checks -- no Sectors API key or credits needed.

Run from backend/:  .venv\\Scripts\\python.exe test_users.py
"""
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["USERS_DB_PATH"] = os.path.join(_tmp, "users_test.db")
os.environ["APP_PASSWORD"] = "test-password-123"
os.environ["AUTH_SECRET"] = "test-secret"
os.environ["LOGIN_MAX_FAILURES"] = "3"
os.environ["RATE_LIMIT_REQUESTS"] = "1000"

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import verify_token  # noqa: E402
from app.main import admin_only, app, user_only  # noqa: E402
from app.users import User, issue_user_token, user_store  # noqa: E402


@app.get("/api/_user_test", dependencies=user_only)
async def _user_test() -> dict:
    return {"ok": True}


@app.post("/api/admin/_test2", dependencies=admin_only)
async def _admin_test() -> dict:
    return {"ok": True}


c = TestClient(app)
creds = {"username": "trevin", "password": "s3cret-pass"}

# 1. Register -> 201 + token; duplicate (case-insensitive) -> 409.
r = c.post("/api/auth/register", json=creds)
assert r.status_code == 201, r.text
body = r.json()
assert body["user"]["username"] == "trevin" and body["access_token"]
assert c.post("/api/auth/register", json={**creds, "username": "TREVIN"}).status_code == 409

# 2. Validation: short password / bad username -> 422.
assert c.post("/api/auth/register", json={"username": "ab", "password": "12345678"}).status_code == 422
assert c.post("/api/auth/register", json={"username": "x y z", "password": "12345678"}).status_code == 422
assert c.post("/api/auth/register", json={"username": "abcd", "password": "short"}).status_code == 422

# 3. Login: right -> token that works on /me and user routes; wrong -> 401.
r = c.post("/api/auth/login", json=creds)
assert r.status_code == 200, r.text
tok = r.json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
me = c.get("/api/auth/me", headers=h)
assert me.status_code == 200 and me.json()["username"] == "trevin", me.text
assert c.get("/api/_user_test", headers=h).status_code == 200
assert c.post("/api/auth/login", json={**creds, "password": "wrong-pass"}).status_code == 401
assert c.post("/api/auth/login", json={"username": "nobody", "password": "whatever1"}).status_code == 401

# 4. No / bogus / expired token -> 401.
assert c.get("/api/auth/me").status_code == 401
assert c.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
u = user_store.get(me.json()["id"])
expired, _ = issue_user_token(u, now=0)
assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
# Token for a user id that doesn't exist -> 401.
ghost, _ = issue_user_token(User(id=999999, username="ghost", created_at=0))
assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401

# 5. A user token must NOT open admin routes.
assert not verify_token(tok)
assert c.post("/api/admin/_test2", headers=h).status_code == 401

# 6. Data routes remain public.
assert c.get("/api/company/BB!!").status_code == 400

# 7. Brute-force guard trips on user login too.
for _ in range(3):
    c.post("/api/auth/login", json={**creds, "password": "wrong-pass"})
assert c.post("/api/auth/login", json=creds).status_code == 429

print("OK -- users: register, duplicate, validation, login, /me, token checks, admin isolation, brute-force guard.")
