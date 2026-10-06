import type { AgentKey, Regime, RegimeColor, SubScoreKey } from '../api/types';

export const palette = {
  bg: '#0a1020',
  panel: '#111b2e',
  border: '#1f2e4a',
  text: '#dde4f2',
  dim: '#8e9dba',
  cyan: '#45b8a8',
  yellow: '#6a9ee0',
  amber: '#dca24e',
  red: '#df7b7b',
  grey: '#5f7090',
} as const;

export const REGIME_HEX: Record<RegimeColor, string> = {
  green: palette.cyan,
  yellow: palette.yellow,
  amber: palette.amber,
  red: palette.red,
};

export function colorHex(color: string | null | undefined): string {
  return REGIME_HEX[color as RegimeColor] ?? palette.grey;
}

export const REGIME_COLOR_KEY: Record<Regime, RegimeColor> = {
  Accumulation: 'green',
  Recovery: 'yellow',
  Distribution: 'amber',
  Stress: 'red',
};

export const REGIMES: Regime[] = ['Accumulation', 'Recovery', 'Distribution', 'Stress'];

export const REGIME_MEANING: Record<Regime, string> = {
  Accumulation: 'Strong fundamentals and momentum. Investors are likely building positions.',
  Recovery: 'Improving, but not confirmed yet. Worth watching.',
  Distribution: 'Weakening signals. Investors may be taking profits or leaving.',
  Stress: 'Several red flags across debt, quality and momentum. High risk.',
};

export const REGIME_RANGE: Record<Regime, string> = {
  Accumulation: '70–100',
  Recovery: '50–69.9',
  Distribution: '30–49.9',
  Stress: '0–29.9',
};

export const REGIME_TICKS = [30, 50, 70] as const;

export const LOW_SIGNAL_THRESHOLD = 0.6;

export const SUB_SCORE_KEYS: SubScoreKey[] = [
  'valuation',
  'momentum',
  'debt',
  'quality',
  'profitability',
];

export const SUB_SCORE_META: Record<SubScoreKey, { label: string; short: string; measures: string; high: string }> = {
  valuation: {
    label: 'Valuation',
    short: 'VAL',
    measures: 'Forward P/E on a 5–25 band',
    high: 'The stock is cheap',
  },
  momentum: {
    label: 'Momentum',
    short: 'MOM',
    measures: 'Position within the 52-week range, plus recent drift',
    high: 'Healthy uptrend',
  },
  debt: {
    label: 'Debt',
    short: 'DEBT',
    measures: 'Debt-to-equity ratio (0 is best, 2.5+ is worst)',
    high: 'Low leverage',
  },
  quality: {
    label: 'Quality',
    short: 'QUAL',
    measures: 'Return on equity (25% ROE = full marks)',
    high: 'Strong returns to shareholders',
  },
  profitability: {
    label: 'Profitability',
    short: 'PROF',
    measures: 'Return on assets (15% ROA = full marks)',
    high: 'Efficient use of assets',
  },
};

export const AGENT_META: Record<AgentKey, { label: string; color: string }> = {
  panic_sellers: { label: 'Panic sellers', color: palette.red },
  momentum_buyers: { label: 'Momentum buyers', color: palette.cyan },
  value_buyers: { label: 'Value buyers', color: '#6b8fd6' },
  profit_takers: { label: 'Profit takers', color: palette.amber },
  passive_holders: { label: 'Passive holders', color: palette.grey },
};

export const AGENT_KEYS: AgentKey[] = [
  'panic_sellers',
  'momentum_buyers',
  'value_buyers',
  'profit_takers',
  'passive_holders',
];

export function thermalColor(score: number): string {
  const stops: [number, string][] = [
    [0, palette.red],
    [35, palette.amber],
    [55, palette.yellow],
    [80, palette.cyan],
  ];
  const s = Math.max(0, Math.min(100, score));
  for (let i = 1; i < stops.length; i++) {
    const [p1, c1] = stops[i];
    const [p0, c0] = stops[i - 1];
    if (s <= p1) return mixHex(c0, c1, (s - p0) / (p1 - p0));
  }
  return stops[stops.length - 1][1];
}

function mixHex(a: string, b: string, t: number): string {
  const pa = parseInt(a.slice(1), 16);
  const pb = parseInt(b.slice(1), 16);
  const ch = (p: number, shift: number) => (p >> shift) & 0xff;
  const lerp = (x: number, y: number) => Math.round(x + (y - x) * t);
  const r = lerp(ch(pa, 16), ch(pb, 16));
  const g = lerp(ch(pa, 8), ch(pb, 8));
  const bl = lerp(ch(pa, 0), ch(pb, 0));
  return `#${((1 << 24) | (r << 16) | (g << 8) | bl).toString(16).slice(1)}`;
}

export function isFinancialSector(sector: string | null | undefined): boolean {
  return !!sector && /financ|bank/i.test(sector);
}
