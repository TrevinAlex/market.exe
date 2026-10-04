// Response shapes from the MARKET.EXE FastAPI backend (backend/app/api/schemas.py).
// The frontend only displays these values; it never recomputes scores.

export type Regime = 'Accumulation' | 'Recovery' | 'Distribution' | 'Stress';
export type RegimeColor = 'green' | 'yellow' | 'amber' | 'red';

export type SubScoreKey = 'valuation' | 'momentum' | 'debt' | 'quality' | 'profitability';
export type SubScores = Record<SubScoreKey, number>;

export interface Score {
  symbol: string; // "BBCA.JK" or "BBCA"
  company_name: string;
  sector: string | null;
  sub_sector: string | null;
  composite: number; // 0–100
  regime: Regime;
  color: RegimeColor;
  sub_scores: SubScores; // each 0–20
  sub_scores_normalized: Record<string, number>; // same keys, 0–1
  confidence: number; // 0–1
  last_close_price: number | null; // IDR
}

export interface ScreenResponse {
  count: number;
  results: Score[];
}

export interface SectorRegime {
  sector: string;
  total: number;
  distribution: Record<string, number>; // regime label -> count
  avg_score: number; // 0–100
  stressed_pct: number; // % of stocks in Stress or Distribution (0–100)
}

export interface HeatmapResponse {
  sectors: SectorRegime[];
}

export interface AgentMix {
  panic_sellers: number;
  momentum_buyers: number;
  value_buyers: number;
  profit_takers: number;
  passive_holders: number;
}

export type AgentKey = keyof AgentMix;

export interface Bands {
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
}

export interface SimulationResponse {
  symbol: string;
  current_price: number;
  horizon_days: number;
  runs: number;
  agents: number;
  agent_mix: AgentMix; // fractions summing to 1
  bands: Bands; // final-day prices
  expected_return_pct: number;
  prob_price_up: number; // 0–1
  sample_paths: number[][]; // each length days + 1
}

export interface SimulateOptions {
  runs?: number;
  days?: number;
}
