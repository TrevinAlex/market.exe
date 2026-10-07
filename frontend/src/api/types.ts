
export type Regime = 'Accumulation' | 'Recovery' | 'Distribution' | 'Stress';
export type RegimeColor = 'green' | 'yellow' | 'amber' | 'red';

export type SubScoreKey = 'valuation' | 'momentum' | 'debt' | 'quality' | 'profitability';
export type SubScores = Record<SubScoreKey, number>;

export interface Score {
  symbol: string;
  company_name: string;
  sector: string | null;
  sub_sector: string | null;
  composite: number;
  regime: Regime;
  color: RegimeColor;
  sub_scores: SubScores;
  sub_scores_normalized: Record<string, number>;
  confidence: number;
  last_close_price: number | null;
  breakdown?: Partial<Record<SubScoreKey, { input: string | null; rule: string }>> | null;
}

export interface ScreenResponse {
  count: number;
  results: Score[];
}

export interface SectorRegime {
  sector: string;
  total: number;
  distribution: Record<string, number>;
  avg_score: number;
  stressed_pct: number;
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
  day: number;
  type: string;
  amount: number;
}

export interface ScenarioResult {
  id: string;
  label: string;
  window: string;
  description: string;
  fit_inside_p10_p90: number;
  fit_n: number;
  historical_median_return_pct: number;
  daily_vol: number;
  agent_mix: AgentMix;
  bands: Bands;
  daily_bands: Record<keyof Bands, number[]>;
  expected_return_pct: number;
  prob_price_up: number;
  sample_paths: number[][];
}

export interface Liquidity {
  avg_daily_value: number;
  avg_daily_volume: number;
  days: number;
}

export interface SimulationResponse {
  symbol: string;
  current_price: number;
  horizon_days: number;
  runs: number;
  agents: number;
  daily_vol?: number;
  vol_method?: string;
  events?: SimEvent[];
  agent_mix: AgentMix;
  bands: Bands;
  daily_bands?: Record<keyof Bands, number[]> | null;
  expected_return_pct: number;
  prob_price_up: number;
  sample_paths: number[][];
  fundamentals?: FundamentalsYear[];
  fundamentals_trend?: 'improving' | 'stable' | 'deteriorating' | null;
  scenarios?: ScenarioResult[];
  liquidity?: Liquidity | null;
}

export interface FundamentalsYear {
  year: number;
  roe: number | null;
  roa: number | null;
  der: number | null;
  pe: number | null;
  valuation: number;
  debt: number;
  quality: number;
  profitability: number;
  score: number | null;
}

export interface SimulateOptions {
  runs?: number;
  days?: number;
}

export interface User {
  id: number;
  username: string;
  created_at: number;
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: User;
}

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
  created_at: string;
}

export interface HistoryResponse {
  total: number;
  results: HistoryEntry[];
}

export interface Pin {
  symbol: string;
  created_at: string;
  score: Score | null;
}

export interface PinsResponse {
  max_pins: number;
  pins: Pin[];
}
