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
  /** Raw input + scoring rule per sub-score ("Why this score"). Missing on older responses. */
  breakdown?: Partial<Record<SubScoreKey, { input: string | null; rule: string }>> | null;
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

export interface SimEvent {
  day: number; // trading day inside the horizon (1 = next trading day)
  type: string; // "dividend"
  amount: number; // IDR per share
}

export interface SimulationResponse {
  symbol: string;
  current_price: number;
  horizon_days: number;
  runs: number;
  agents: number;
  daily_vol?: number; // per trading day, 0.02 = 2%
  vol_method?: string; // "ml" | "range" | "default"
  events?: SimEvent[];
  agent_mix: AgentMix; // fractions summing to 1
  bands: Bands; // final-day prices
  daily_bands?: Record<keyof Bands, number[]> | null; // per day 0..horizon
  expected_return_pct: number;
  prob_price_up: number; // 0–1
  sample_paths: number[][]; // each length days + 1
}

export interface SimulateOptions {
  runs?: number;
  days?: number;
}

// --- user accounts (backend/app/users.py) ---
export interface User {
  id: number;
  username: string;
  created_at: number; // unix seconds
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number; // seconds
  user: User;
}

// --- user history (GET /api/history) ---
export type HistoryKind = 'company' | 'simulation';

export interface HistoryEntry {
  id: number;
  kind: HistoryKind;
  symbol: string;
  params: { runs?: number; days?: number };
  result: {
    company_name?: string;
    composite?: number;
    regime?: Regime;
    last_close_price?: number | null;
    current_price?: number;
    expected_return_pct?: number;
    prob_price_up?: number;
    p50?: number;
  };
  created_at: string; // ISO-8601
}

export interface HistoryResponse {
  total: number;
  results: HistoryEntry[];
}

// --- pinned stocks (GET /api/pins) ---
export interface Pin {
  symbol: string; // bare ticker, e.g. "BBCA"
  created_at: string; // ISO-8601
  score: Score | null; // only with ?scores=true; null if unavailable
}

export interface PinsResponse {
  max_pins: number;
  pins: Pin[];
}
