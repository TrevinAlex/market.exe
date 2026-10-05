"""MARKET.EXE backend — FastAPI app.

Endpoints
---------
GET  /health                      liveness probe
GET  /api/screen                  score & rank companies (optionally filtered)
GET  /api/company/{symbol}        score a single company
GET  /api/heatmap                 sector-level regime distribution
POST /api/simulate/{symbol}       run the ABM Monte Carlo for one stock
POST /api/admin/login             exchange APP_PASSWORD for an admin bearer token

Data routes are public. Admin/edit routes use ``dependencies=admin_only`` and
require ``Authorization: Bearer <token>`` (see app/auth.py).

The scoring + simulation logic lives in app/core; this module only wires HTTP
to it and handles API errors from the upstream Sectors API.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.api.schemas import (
    HeatmapResponse,
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
from app.core.scoring import flatten_report, score_company
from app.core.simulation import run_simulation
from app.security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    safe_detail,
    validate_index,
    validate_symbol,
)
from app.services.sectors_client import sectors_client

app = FastAPI(
    title="MARKET.EXE",
    description="IDX stock health regime scanner + agent-based scenario simulator.",
    version="0.1.0",
    docs_url=None,   # disable the CDN-backed default; served locally below
    redoc_url=None,
)

# Serve Swagger UI assets locally (no CDN dependency — works offline).
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

# --- security middleware (order: added last runs first) -------------------
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# CORS restricted to configured origins (set ALLOWED_ORIGINS in .env).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_methods=["GET", "POST"],
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


# Attach to any future admin/edit route: @app.post(..., dependencies=admin_only)
# Data routes below are public -- anyone can view without logging in.
admin_only = [Depends(require_admin)]


async def _safe_screen(base_where: str | None, limit: int, offset: int):
    try:
        return await sectors_client.screen_scored(
            base_where=base_where, limit=limit, offset=offset
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=safe_detail(f"Sectors API error {e.response.status_code}", e),
        ) from e
    except httpx.HTTPError as e:
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
    # Only a validated index token is interpolated into the upstream filter;
    # arbitrary client-supplied `where` clauses are no longer accepted.
    effective_where = f"indices in ['{index}']" if index else "market_cap IS NOT NULL"

    raw = await _safe_screen(effective_where, limit, offset)
    scored = [score_company(c) for c in raw]

    if sort == "score":
        scored.sort(key=lambda s: s.composite, reverse=True)

    results = [ScoreModel(**s.to_dict()) for s in scored]
    return ScreenResponse(count=len(results), results=results)


@app.get("/api/company/{symbol}", response_model=ScoreModel)
async def company(symbol: str) -> ScoreModel:
    symbol = validate_symbol(symbol)
    try:
        report = await sectors_client.company_report(symbol)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=safe_detail("Sectors API request failed", e)
        ) from e
    if not report:
        raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found on IDX.")
    return ScoreModel(**score_company(flatten_report(report)).to_dict())


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
    sectors.sort(key=lambda x: x.avg_score)  # most stressed sectors first
    return HeatmapResponse(sectors=sectors)


@app.post("/api/simulate/{symbol}", response_model=SimulationResponse)
async def simulate(
    symbol: str,
    runs: int = Query(default=500, ge=50, le=2000),
    days: int = Query(default=30, ge=5, le=120),
) -> SimulationResponse:
    """Score a stock, then run the agent-based Monte Carlo scenario engine."""
    symbol = validate_symbol(symbol)
    try:
        report = await sectors_client.company_report(symbol)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=safe_detail("Sectors API request failed", e)
        ) from e
    if not report:
        raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found on IDX.")

    result = score_company(flatten_report(report))
    sim = run_simulation(
        current_price=result.last_close_price or 0.0,
        sub_scores_norm=result.sub_scores.normalized(),
        runs=runs,
        days=days,
    )
    return SimulationResponse(symbol=result.symbol, **sim)
