"""Regular user accounts: register + login with username/password.

Separate from the admin login in app/auth.py:

* Users are stored in a local SQLite file (USERS_DB_PATH), stdlib only.
* Passwords are hashed with scrypt (hashlib) + a per-user random salt.
* User tokens are HMAC-signed with a key *different* from the admin key and
  carry ``typ="user"``, so a user token can never pass ``require_admin``.

Endpoints (wired in main.py)
----------------------------
POST /api/auth/register   {username, password} -> token
POST /api/auth/login      {username, password} -> token
GET  /api/auth/me         Bearer token -> {id, username, created_at}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import _SECRET, _b64, _unb64
from app.config import settings

_USER_KEY = hashlib.sha256(_SECRET + b"|user-tokens").digest()

_bearer = HTTPBearer(auto_error=False, description="Token from POST /api/auth/login")

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


@dataclass(frozen=True)
class User:
    id: int
    username: str
    created_at: int
    uid: str = ""




def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return f"scrypt${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_b64, dk_b64 = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    expected = hash_password(password, _unb64(salt_b64)).split("$")[2]
    return hmac.compare_digest(expected, dk_b64)


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))




class UserStore:
    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                   id            INTEGER PRIMARY KEY AUTOINCREMENT,
                   username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                   password_hash TEXT NOT NULL,
                   created_at    INTEGER NOT NULL
               )"""
        )
        cols = {r[1] for r in self._db.execute("PRAGMA table_info(users)")}
        if "uid" not in cols:
            self._db.execute("ALTER TABLE users ADD COLUMN uid TEXT")
        for (row_id,) in self._db.execute("SELECT id FROM users WHERE uid IS NULL").fetchall():
            self._db.execute("UPDATE users SET uid = ? WHERE id = ?", (str(uuid.uuid4()), row_id))
        self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_uid_idx ON users (uid)")
        self._db.commit()

    def create(self, username: str, password: str) -> User | None:
        """Insert a user. Returns None if the username is already taken."""
        pw_hash = hash_password(password)
        now = int(time.time())
        uid = str(uuid.uuid4())
        with self._lock:
            try:
                cur = self._db.execute(
                    "INSERT INTO users (username, password_hash, created_at, uid) VALUES (?, ?, ?, ?)",
                    (username, pw_hash, now, uid),
                )
                self._db.commit()
            except sqlite3.IntegrityError:
                return None
        return User(id=cur.lastrowid, username=username, created_at=now, uid=uid)

    def authenticate(self, username: str, password: str) -> User | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, username, password_hash, created_at, uid FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            verify_password(password, _DUMMY_HASH)
            return None
        if not verify_password(password, row[2]):
            return None
        return User(id=row[0], username=row[1], created_at=row[3], uid=row[4])

    def get(self, user_id: int) -> User | None:
        with self._lock:
            row = self._db.execute(
                "SELECT id, username, created_at, uid FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return User(*row) if row else None


user_store = UserStore(settings.users_db_path)




def _sign(payload: str) -> str:
    return _b64(hmac.new(_USER_KEY, payload.encode(), hashlib.sha256).digest())


def issue_user_token(user: User, now: float | None = None) -> tuple[str, int]:
    ttl = settings.auth_token_ttl_seconds
    exp = int((time.time() if now is None else now) + ttl)
    payload = _b64(json.dumps({"typ": "user", "sub": user.id, "exp": exp}).encode())
    return f"{payload}.{_sign(payload)}", ttl


def verify_user_token(token: str, now: float | None = None) -> int | None:
    """Return the user id if the token is valid, else None."""
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
        if data["typ"] != "user":
            return None
        exp, sub = int(data["exp"]), int(data["sub"])
    except (ValueError, KeyError, TypeError):
        return None
    return sub if exp > (time.time() if now is None else now) else None


def _user_from_creds(creds: HTTPAuthorizationCredentials | None) -> User | None:
    uid = (
        verify_user_token(creds.credentials)
        if creds is not None and creds.scheme.lower() == "bearer"
        else None
    )
    return user_store.get(uid) if uid is not None else None


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    """FastAPI dependency: the logged-in user, or None for anonymous visitors."""
    return _user_from_creds(creds)


def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """FastAPI dependency: the logged-in user, or 401."""
    user = _user_from_creds(creds)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
