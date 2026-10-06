"""MARKET.EXE backend — FastAPI app.

Endpoints
---------
GET  /health                      liveness probe
GET  /api/screen                  score & rank companies (optionally filtered)
GET  /api/company/{symbol}        score a single company
GET  /api/heatmap                 sector-level regime distribution
POST /api/simulate/{symbol}       run the ABM Monte Carlo for one stock
POST /api/admin/login             exchange APP_PASSWORD for an admin bearer token
POST /api/auth/register           create a user account -> user bearer token
POST /api/auth/login              username + password -> user bearer token
GET  /api/auth/me                 current user (needs user bearer token)
GET  /api/history                 logged-in user's activity (Supabase)
DELETE /api/history[/{id}]        clear all / one history entry
GET  /api/pins[?scores=true]      logged-in user's pinned stocks (Supabase)
PUT  /api/pins/{symbol}           pin a stock
DELETE /api/pins/{symbol}         unpin a stock

Company lookups and simulations made while logged in are saved to history.

Data routes are public. Admin/edit routes use ``dependencies=admin_only`` and
require ``Authorization: Bearer <token>`` (see app/auth.py).

The scoring + simulation logic lives in app/core; this module only wires HTTP
to it and handles API errors from the upstream Sectors API.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from typing import Literal

from pathlib import Path

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.api.schemas import (
    HeatmapResponse,
    HistoryEntry,
    HistoryResponse,
    PinModel,
    PinsResponse,
    ScoreModel,
    ScreenResponse,
    SectorRegimeModel,
    SimulationResponse,
)
from app.auth import (
    check_password,
    clear_failures,
    guard_login_attempt,
    issue_token,
    record_failure,
    require_admin,
)
from app.config import settings
from app.core.scoring import flatten_report, fundamentals_history, score_company
from app.core.simulation import predict_daily_vol, run_simulation, upcoming_dividends
from app.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    safe_detail,
    validate_index,
    validate_symbol,
)
from app.services.sectors_client import sectors_client
from app.services.history import history_store
from app.services.pins import PinLimitError, pin_store
from app.users import User, issue_user_token, optional_user, require_user, user_store

app = FastAPI(
    title="MARKET.EXE",
    description="IDX stock health regime scanner + agent-based scenario simulator.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


_DOCS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MARKET.EXE — API docs</title>
  <link rel="stylesheet" href="/static/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="/static/swagger-ui-bundle.js"></script>
  <script src="/static/swagger-init.js"></script>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html() -> HTMLResponse:
    """Swagger UI from local assets only — no CDN, no inline script (CSP-safe)."""
    return HTMLResponse(_DOCS_HTML)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """Landing index — lists the live endpoints so the base URL isn't a 404."""
    return {
        "service": "MARKET.EXE",
        "description": "IDX stock health regime scanner + agent-based scenario simulator.",
        "docs": "/docs",
        "admin": "POST /api/admin/login {\"password\": ...} -> token for admin-only routes",
        "auth": {
            "register": "POST /api/auth/register {\"username\": ..., \"password\": ...}",
            "login": "POST /api/auth/login {\"username\": ..., \"password\": ...}",
            "me": "GET /api/auth/me  (Authorization: Bearer <token>)",
        },
        "endpoints": {
            "liveness": "GET /health",
            "screen": "GET /api/screen?index=LQ45&limit=10",
            "company": "GET /api/company/{symbol}  e.g. /api/company/BBCA",
            "heatmap": "GET /api/heatmap?index=LQ45",
            "simulate": "POST /api/simulate/{symbol}?runs=500&days=30",
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "market.exe"}


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@app.post("/api/admin/login", response_model=LoginResponse)
async def admin_login(body: LoginRequest, request: Request) -> LoginResponse:
    """Exchange the admin password (APP_PASSWORD) for a bearer token.

    Only admin routes need this token; all data routes are public.
    """
    if not settings.app_password:
        raise HTTPException(status_code=503, detail="Admin login is not configured.")
    ip = guard_login_attempt(request)
    if not check_password(body.password):
        record_failure(ip)
        raise HTTPException(status_code=401, detail="Wrong password.")
    clear_failures(ip)
    token, ttl = issue_token()
    return LoginResponse(access_token=token, expires_in=ttl)




class UserCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


class UserModel(BaseModel):
    id: int
    username: str
    created_at: int


class UserAuthResponse(LoginResponse):
    user: UserModel


def _user_auth_response(user: User) -> UserAuthResponse:
    token, ttl = issue_user_token(user)
    return UserAuthResponse(
        access_token=token,
        expires_in=ttl,
        user=UserModel(id=user.id, username=user.username, created_at=user.created_at),
    )


@app.post("/api/auth/register", response_model=UserAuthResponse, status_code=201)
async def user_register(body: UserCredentials) -> UserAuthResponse:
    """Create a user account and return a bearer token (auto-login)."""
    user = user_store.create(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=409, detail="Username is already taken.")
    return _user_auth_response(user)


@app.post("/api/auth/login", response_model=UserAuthResponse)
async def user_login(body: UserCredentials, request: Request) -> UserAuthResponse:
    """Exchange username + password for a user bearer token."""
    ip = guard_login_attempt(request)
    user = user_store.authenticate(body.username, body.password)
    if user is None:
        record_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    clear_failures(ip)
    return _user_auth_response(user)


@app.get("/api/auth/me", response_model=UserModel)
async def user_me(user: User = Depends(require_user)) -> UserModel:
    """Return the currently logged-in user."""
    return UserModel(id=user.id, username=user.username, created_at=user.created_at)


user_only = [Depends(require_user)]

admin_only = [Depends(require_admin)]


_log = logging.getLogger("uvicorn.error")


def _log_sectors_error(e: httpx.HTTPError) -> None:
    if isinstance(e, httpx.HTTPStatusError):
        _log.warning(
            "Sectors API returned %s for %s: %s",
            e.response.status_code,
            e.request.url.path,
            e.response.text[:300],
        )
    else:
        _log.warning("Sectors API request failed: %s: %s", type(e).__name__, e)


async def _safe_screen(base_where: str | None, limit: int, offset: int):
    try:
        return await sectors_client.screen_scored(
            base_where=base_where, limit=limit, offset=offset
        )
    except httpx.HTTPStatusError as e:
        _log_sectors_error(e)
        raise HTTPException(
            status_code=502,
            detail=safe_detail(f"Sectors API error {e.response.status_code}", e),
        ) from e
    except httpx.HTTPError as e:
        _log_sectors_error(e)
        raise HTTPException(
            status_code=502, detail=safe_detail("Sectors API request failed", e)
        ) from e


@app.get("/api/screen", response_model=ScreenResponse)
async def screen(
    index: str | None = Query(
        default=None, description="Restrict to an IDX index like LQ45 or IDX30."
    ),
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="score", description="'score' (default) or 'market_cap'."),
) -> ScreenResponse:
    """Fetch companies, score every one, and return them ranked by health score."""
    index = validate_index(index)
    effective_where = f"indices in ['{index}']" if index else "market_cap IS NOT NULL"

    raw = await _safe_screen(effective_where, limit, offset)
    scored = [score_company(c) for c in raw]

    if sort == "score":
        scored.sort(key=lambda s: s.composite, reverse=True)

    results = [ScoreModel(**s.to_dict()) for s in scored]
    return ScreenResponse(count=len(results), results=results)


@app.get("/api/company/{symbol}", response_model=ScoreModel)
async def company(
    symbol: str,
    background: BackgroundTasks,
    user: User | None = Depends(optional_user),
) -> ScoreModel:
    symbol = validate_symbol(symbol)
    try:
        report = await sectors_client.company_report(symbol)
    except httpx.HTTPError as e:
        _log_sectors_error(e)
        raise HTTPException(
            status_code=502, detail=safe_detail("Sectors API request failed", e)
        ) from e
    if not report:
        raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found on IDX.")
    score = ScoreModel(**score_company(flatten_report(report)).to_dict())
    if user:
        background.add_task(
            history_store.record,
            user.uid,
            "company",
            _ticker(symbol),
            {},
            {
                "company_name": score.company_name,
                "composite": score.composite,
                "regime": score.regime,
                "last_close_price": score.last_close_price,
            },
        )
    return score


@app.get("/api/heatmap", response_model=HeatmapResponse)
async def heatmap(
    index: str | None = Query(default="LQ45", description="IDX index to aggregate, e.g. LQ45."),
    limit: int = Query(default=100, ge=1, le=200),
) -> HeatmapResponse:
    """Aggregate regime distribution per sector — a macro market signal."""
    index = validate_index(index)
    where = f"indices in ['{index}']" if index else "market_cap IS NOT NULL"
    raw = await _safe_screen(where, limit, 0)
    scored = [score_company(c) for c in raw]

    by_sector: dict[str, list] = defaultdict(list)
    for s in scored:
        by_sector[s.sector or "Unknown"].append(s)

    sectors: list[SectorRegimeModel] = []
    for sector, members in by_sector.items():
        dist = Counter(m.regime for m in members)
        total = len(members)
        stressed = dist.get("Stress", 0) + dist.get("Distribution", 0)
        sectors.append(
            SectorRegimeModel(
                sector=sector,
                total=total,
                distribution=dict(dist),
                avg_score=round(sum(m.composite for m in members) / total, 2),
                stressed_pct=round(stressed / total * 100, 1),
            )
        )
    sectors.sort(key=lambda x: x.avg_score)
    return HeatmapResponse(sectors=sectors)


@app.post("/api/simulate/{symbol}", response_model=SimulationResponse)
async def simulate(
    symbol: str,
    background: BackgroundTasks,
    runs: int = Query(default=500, ge=50, le=2000),
    days: int = Query(default=30, ge=5, le=120),
    user: User | None = Depends(optional_user),
) -> SimulationResponse:
    """Score a stock, then run the agent-based Monte Carlo scenario engine."""
    symbol = validate_symbol(symbol)
    try:
        report = await sectors_client.company_report(symbol)
    except httpx.HTTPError as e:
        _log_sectors_error(e)
        raise HTTPException(
            status_code=502, detail=safe_detail("Sectors API request failed", e)
        ) from e
    if not report:
        raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found on IDX.")

    flat = flatten_report(report)
    result = score_company(flat)

    closes_res, actions_res = await asyncio.gather(
        sectors_client.daily_closes(symbol),
        sectors_client.corporate_actions(symbol),
        return_exceptions=True,
    )
    closes = closes_res if isinstance(closes_res, list) else None
    actions = actions_res if isinstance(actions_res, dict) else None
    daily_vol, vol_method = predict_daily_vol(
        closes, flat.get("52_w_high_price"), flat.get("52_w_low_price")
    )
    sim = run_simulation(
        current_price=result.last_close_price or 0.0,
        sub_scores_norm=result.sub_scores.normalized(),
        runs=runs,
        days=days,
        daily_vol=daily_vol,
        vol_method=vol_method,
        dividends=upcoming_dividends(actions, days),
    )
    if user:
        background.add_task(
            history_store.record,
            user.uid,
            "simulation",
            _ticker(symbol),
            {"runs": runs, "days": days},
            {
                "company_name": result.company_name,
                "composite": result.composite,
                "regime": result.regime,
                "current_price": sim["current_price"],
                "expected_return_pct": sim["expected_return_pct"],
                "prob_price_up": sim["prob_price_up"],
                "p50": sim["bands"]["p50"],
            },
        )
    fund = fundamentals_history(report)
    return SimulationResponse(
        symbol=result.symbol,
        **sim,
        fundamentals=fund["years"],
        fundamentals_trend=fund["trend"],
    )




def _ticker(symbol: str) -> str:
    return symbol.upper().removesuffix(".JK")


def _require_history() -> None:
    if not history_store.enabled:
        raise HTTPException(status_code=503, detail="History is not configured.")


async def _supabase_call(coro):
    try:
        return await coro
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=safe_detail("Database (Supabase) error", e)) from e


@app.get(
    "/api/history",
    response_model=HistoryResponse,
    dependencies=[Depends(_require_history)],
)
async def history_list(
    user: User = Depends(require_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    kind: Literal["company", "simulation"] | None = Query(default=None),
) -> HistoryResponse:
    """The logged-in user's own activity, newest first."""
    rows, total = await _supabase_call(history_store.list(user.uid, limit, offset, kind))
    return HistoryResponse(total=total, results=[HistoryEntry(**r) for r in rows])


@app.delete("/api/history", dependencies=[Depends(_require_history)])
async def history_clear(user: User = Depends(require_user)) -> dict:
    """Delete all of the logged-in user's history."""
    return {"deleted": await _supabase_call(history_store.delete(user.uid))}


@app.delete("/api/history/{entry_id}", dependencies=[Depends(_require_history)])
async def history_delete(entry_id: int, user: User = Depends(require_user)) -> dict:
    """Delete one history entry (only if it belongs to the logged-in user)."""
    n = await _supabase_call(history_store.delete(user.uid, entry_id))
    if n == 0:
        raise HTTPException(status_code=404, detail="History entry not found.")
    return {"deleted": n}




def _require_pins() -> None:
    if not pin_store.enabled:
        raise HTTPException(status_code=503, detail="Pins are not configured.")


async def _score_one(symbol: str) -> ScoreModel | None:
    """Score a pinned stock. None if it can't be fetched (delisted, API down)."""
    try:
        report = await sectors_client.company_report(symbol)
    except httpx.HTTPError:
        return None
    if not report:
        return None
    return ScoreModel(**score_company(flatten_report(report)).to_dict())


@app.get("/api/pins", response_model=PinsResponse, dependencies=[Depends(_require_pins)])
async def pins_list(
    user: User = Depends(require_user),
    scores: bool = Query(
        default=False,
        description="Also score every pinned stock (4 Sectors credits each, cached).",
    ),
) -> PinsResponse:
    """The logged-in user's pinned stocks, in the order they were pinned."""
    rows = await _supabase_call(pin_store.list(user.uid))
    pins = [PinModel(**r) for r in rows]
    if scores and pins:
        sem = asyncio.Semaphore(5)

        async def bounded(sym: str):
            async with sem:
                return await _score_one(sym)

        for pin, score in zip(pins, await asyncio.gather(*(bounded(p.symbol) for p in pins))):
            pin.score = score
    return PinsResponse(max_pins=pin_store.max_pins, pins=pins)


@app.put("/api/pins/{symbol}", dependencies=[Depends(_require_pins)])
async def pins_add(symbol: str, user: User = Depends(require_user)) -> dict:
    """Pin a stock (idempotent)."""
    sym = _ticker(validate_symbol(symbol))
    try:
        added = await _supabase_call(pin_store.add(user.uid, sym))
    except PinLimitError:
        raise HTTPException(
            status_code=409, detail=f"Pin limit reached ({pin_store.max_pins}). Unpin a stock first."
        )
    return {"symbol": sym, "pinned": True, "added": added}


@app.delete("/api/pins/{symbol}", dependencies=[Depends(_require_pins)])
async def pins_remove(symbol: str, user: User = Depends(require_user)) -> dict:
    """Unpin a stock (idempotent)."""
    sym = _ticker(validate_symbol(symbol))
    removed = await _supabase_call(pin_store.remove(user.uid, sym))
    return {"symbol": sym, "pinned": False, "removed": removed}
