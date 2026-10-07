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
    input: str | None = None
    rule: str


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
    day: int
    type: str
    amount: float


class FundamentalsYear(BaseModel):
    year: int
    roe: float | None
    roa: float | None
    der: float | None
    pe: float | None
    valuation: float
    debt: float
    quality: float
    profitability: float
    score: float | None


class ScenarioModel(BaseModel):
    id: str
    label: str
    window: str
    description: str
    fit_inside_p10_p90: float
    fit_n: int
    historical_median_return_pct: float
    daily_vol: float
    agent_mix: AgentMixModel
    bands: BandsModel
    daily_bands: dict[str, list[float]]
    expected_return_pct: float
    prob_price_up: float
    sample_paths: list[list[float]]


class LiquidityModel(BaseModel):
    avg_daily_value: float
    avg_daily_volume: float
    days: int


class SimulationResponse(BaseModel):
    symbol: str
    current_price: float
    horizon_days: int
    runs: int
    agents: int
    daily_vol: float
    vol_method: str
    drift_scale: float
    scenario: str | None = None
    events: list[SimEvent] = []
    agent_mix: AgentMixModel
    bands: BandsModel
    daily_bands: dict[str, list[float]] | None = None
    expected_return_pct: float
    prob_price_up: float
    sample_paths: list[list[float]]
    fundamentals: list[FundamentalsYear] = []
    fundamentals_trend: str | None = None
    scenarios: list[ScenarioModel] = []
    liquidity: LiquidityModel | None = None


class HistoryEntry(BaseModel):
    id: int
    kind: str
    symbol: str
    params: dict[str, Any]
    result: dict[str, Any]
    created_at: str


class HistoryResponse(BaseModel):
    total: int
    results: list[HistoryEntry]


class PinModel(BaseModel):
    symbol: str
    created_at: str
    score: ScoreModel | None = None


class PinsResponse(BaseModel):
    max_pins: int
    pins: list[PinModel]
