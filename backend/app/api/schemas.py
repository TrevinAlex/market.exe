"""Pydantic response models for the API surface."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SubScoresModel(BaseModel):
    valuation: float
    momentum: float
    debt: float
    quality: float
    profitability: float


class SubScoreExplainModel(BaseModel):
    input: str | None = None  # raw value behind the sub-score, e.g. "ROE 18.0%"; None = no data
    rule: str  # how that value maps to 0-20 points


class ScoreModel(BaseModel):
    symbol: str
    company_name: str
    sector: str | None = None
    sub_sector: str | None = None
    composite: float
    regime: str
    color: str
    sub_scores: SubScoresModel
    sub_scores_normalized: dict[str, float]
    confidence: float
    last_close_price: float | None = None
    breakdown: dict[str, SubScoreExplainModel] | None = None


class ScreenResponse(BaseModel):
    count: int
    results: list[ScoreModel]


class SectorRegimeModel(BaseModel):
    sector: str
    total: int
    distribution: dict[str, int]
    avg_score: float
    stressed_pct: float


class HeatmapResponse(BaseModel):
    sectors: list[SectorRegimeModel]


class AgentMixModel(BaseModel):
    panic_sellers: float
    momentum_buyers: float
    value_buyers: float
    profit_takers: float
    passive_holders: float


class BandsModel(BaseModel):
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


class SimEvent(BaseModel):
    day: int  # trading day inside the horizon (1 = next trading day)
    type: str  # "dividend"
    amount: float  # IDR per share


class SimulationResponse(BaseModel):
    symbol: str
    current_price: float
    horizon_days: int
    runs: int
    agents: int
    daily_vol: float  # market-noise volatility used, per trading day (0.02 = 2%)
    vol_method: str  # "ml" (90-day volatility model), "range" (52-week range) or "default"
    drift_scale: float  # share of the agent mix's directional bias kept (0 = none)
    events: list[SimEvent] = []  # known events inside the horizon (e.g. ex-dividend dates)
    agent_mix: AgentMixModel
    bands: BandsModel
    daily_bands: dict[str, list[float]] | None = None  # p10..p90 for every day 0..horizon (fan chart)
    expected_return_pct: float
    prob_price_up: float
    sample_paths: list[list[float]]


class HistoryEntry(BaseModel):
    id: int
    kind: str  # "company" | "simulation"
    symbol: str
    params: dict[str, Any]
    result: dict[str, Any]
    created_at: str  # ISO-8601 timestamp from Postgres


class HistoryResponse(BaseModel):
    total: int
    results: list[HistoryEntry]



class PinModel(BaseModel):
    symbol: str
    created_at: str  # ISO-8601 timestamp from Postgres
    score: ScoreModel | None = None  # only with ?scores=true; None if unavailable


class PinsResponse(BaseModel):
    max_pins: int
    pins: list[PinModel]
