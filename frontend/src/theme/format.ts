const idr = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** Format an IDR price as "Rp 6,100". */
export function formatIdr(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return 'Rp —';
  return `Rp ${idr.format(value)}`;
}

/** Signed percent, e.g. "+2.4%" / "-1.0%". */
export function formatSignedPct(value: number, digits = 1): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : '±';
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

export function formatPct01(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}
