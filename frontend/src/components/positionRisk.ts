import type { Bands } from '../api/types';

export const LOT_SIZE = 100;

export interface Outcome {
  key: 'p10' | 'p50' | 'p90';
  value: number;
  change: number;
  changePct: number;
}

export interface PositionRisk {
  amount: number;
  lots: number;
  outcomes: Outcome[];
}

export function positionRisk(amount: number, currentPrice: number, bands: Bands): PositionRisk | null {
  if (!(amount > 0) || !(currentPrice > 0)) return null;
  const outcomes = (['p10', 'p50', 'p90'] as const).map((key) => {
    const ratio = bands[key] / currentPrice;
    const value = amount * ratio;
    return { key, value, change: value - amount, changePct: (ratio - 1) * 100 };
  });
  return { amount, lots: Math.floor(amount / (currentPrice * LOT_SIZE)), outcomes };
}

export function parseRupiah(text: string): number | null {
  const t = text.trim().toLowerCase().replace(/^rp\s*/, '');
  const m = t.match(/^([\d.,\s]+)\s*(jt|juta|m|mio|rb|ribu|k|b|miliar|bn)?$/);
  if (!m) return null;
  const unit = m[2];
  let num = m[1].replace(/\s/g, '');
  if (unit) {
    num = num.replace(',', '.');
    if ((num.match(/\./g) ?? []).length > 1) return null;
  } else {
    num = num.replace(/[.,]/g, '');
  }
  const base = Number(num);
  if (!Number.isFinite(base) || base <= 0) return null;
  const mult =
    unit === 'jt' || unit === 'juta' || unit === 'm' || unit === 'mio'
      ? 1e6
      : unit === 'rb' || unit === 'ribu' || unit === 'k'
        ? 1e3
        : unit === 'b' || unit === 'miliar' || unit === 'bn'
          ? 1e9
          : 1;
  return Math.round(base * mult);
}

export function formatIdrCompact(value: number, signed = false): string {
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : '';
  const a = Math.abs(value);
  const [n, s] = a >= 1e9 ? [a / 1e9, 'B'] : a >= 1e6 ? [a / 1e6, 'M'] : a >= 1e3 ? [a / 1e3, 'K'] : [a, ''];
  const digits = s && n < 100 ? 1 : 0;
  return `${sign}Rp ${n.toFixed(digits).replace(/\.0$/, '')}${s}`;
}

export const PARTICIPATION = 0.2;

export interface ExitLiquidity {
  shareOfDay: number;
  costPct: number;
  cost: number;
  daysToExit: number;
  level: 'easy' | 'noticeable' | 'hard';
}

export function exitLiquidity(amount: number, avgDailyValue: number, dailyVol: number): ExitLiquidity | null {
  if (!(amount > 0) || !(avgDailyValue > 0) || !(dailyVol > 0)) return null;
  const shareOfDay = amount / avgDailyValue;
  const costPct = dailyVol * Math.sqrt(shareOfDay) * 100;
  return {
    shareOfDay,
    costPct,
    cost: (amount * costPct) / 100,
    daysToExit: Math.max(1, Math.ceil(shareOfDay / PARTICIPATION)),
    level: shareOfDay < 0.01 ? 'easy' : shareOfDay < 0.1 ? 'noticeable' : 'hard',
  };
}

export function formatRupiahInput(text: string, caret: number = text.length): { text: string; caret: number } {
  const body = text.replace(/^\s*rp\s*/i, '');
  if (/[a-z]/i.test(body)) return { text, caret };
  const digits = body.replace(/\D/g, '').replace(/^0+(?=\d)/, '');
  const formatted = digits.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  const dropped = body.replace(/\D/g, '').length - digits.length;
  let want = Math.max(0, text.slice(0, caret).replace(/\D/g, '').length - dropped);
  let pos = 0;
  while (want > 0 && pos < formatted.length) {
    if (/\d/.test(formatted[pos])) want--;
    pos++;
  }
  return { text: formatted, caret: pos };
}
