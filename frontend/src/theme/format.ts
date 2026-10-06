const idr = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

export function formatIdr(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return 'Rp —';
  return `Rp ${idr.format(value)}`;
}

export function formatSignedPct(value: number, digits = 1): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : '±';
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

export function formatPct01(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}
