import type { Bands } from '../api/types';

/** IDX trades in lots of 100 shares. */
export const LOT_SIZE = 100;

export interface Outcome {
  key: 'p10' | 'p50' | 'p90';
  value: number; // what the position would be worth, IDR
  change: number; // value - amount, IDR
  changePct: number; // percent, e.g. -8.2
}

export interface PositionRisk {
  amount: number;
  lots: number; // whole lots the amount buys at today's price
  outcomes: Outcome[];
}

/**
 * What an investment of `amount` would be worth at the simulation's P10 / P50 / P90
 * outcomes. Scales the amount by each band's price change, so a rounding to whole
 * lots doesn't distort small amounts; `lots` is shown alongside for context.
 */
export function positionRisk(amount: number, currentPrice: number, bands: Bands): PositionRisk | null {
  if (!(amount > 0) || !(currentPrice > 0)) return null;
  const outcomes = (['p10', 'p50', 'p90'] as const).map((key) => {
    const ratio = bands[key] / currentPrice;
    const value = amount * ratio;
    return { key, value, change: value - amount, changePct: (ratio - 1) * 100 };
  });
  return { amount, lots: Math.floor(amount / (currentPrice * LOT_SIZE)), outcomes };
}

/** Parse "10.000.000", "10,000,000", "10jt" or "1.5m" into rupiah. Returns null if unreadable. */
export function parseRupiah(text: string): number | null {
  const t = text.trim().toLowerCase().replace(/^rp\s*/, '');
  const m = t.match(/^([\d.,\s]+)\s*(jt|juta|m|mio|rb|ribu|k|b|miliar|bn)?$/);
  if (!m) return null;
  const unit = m[2];
  let num = m[1].replace(/\s/g, '');
  if (unit) {
    // with a unit, allow one decimal separator: "1.5jt" / "1,5jt"
    num = num.replace(',', '.');
    if ((num.match(/\./g) ?? []).length > 1) return null;
  } else {
    // without a unit, dots and commas are thousands separators
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

/** Compact IDR for money amounts: "Rp 1.2M", "Rp 850K", "Rp 3.4B". */
export function formatIdrCompact(value: number, signed = false): string {
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : '';
  const a = Math.abs(value);
  const [n, s] = a >= 1e9 ? [a / 1e9, 'B'] : a >= 1e6 ? [a / 1e6, 'M'] : a >= 1e3 ? [a / 1e3, 'K'] : [a, ''];
  const digits = s && n < 100 ? 1 : 0;
  return `${sign}Rp ${n.toFixed(digits).replace(/\.0$/, '')}${s}`;
}
