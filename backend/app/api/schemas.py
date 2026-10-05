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


class SimulationResponse(BaseModel):
    symbol: str
    current_price: float
    horizon_days: int
    runs: int
    agents: int
    agent_mix: AgentMixModel
    bands: BandsModel
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
