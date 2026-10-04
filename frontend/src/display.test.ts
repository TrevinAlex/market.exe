import { describe, expect, it } from 'vitest';
import { ApiError, baseTicker, normalizeTicker, toApiError } from './api/client';
import { isNoData } from './components/subScoreUtils';
import { formatIdr, formatSignedPct } from './theme/format';
import { colorHex, isFinancialSector, thermalColor } from './theme/tokens';

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });

describe('ticker validation', () => {
  it('accepts exactly 4 letters and uppercases', () => {
    expect(normalizeTicker('bbca')).toBe('BBCA');
    expect(normalizeTicker(' tlkm ')).toBe('TLKM');
  });
  it('rejects anything else', () => {
    for (const bad of ['BBC', 'BBCAA', 'BB1A', 'BB.A', '', 'BBCA.JK']) expect(normalizeTicker(bad)).toBeNull();
  });
  it('strips .JK suffix', () => expect(baseTicker('bbca.JK')).toBe('BBCA'));
});

describe('toApiError', () => {
  it('429 uses Retry-After', async () => {
    const e = await toApiError(json(429, { detail: 'Rate limit exceeded.' }, { 'Retry-After': '17' }));
    expect(e).toBeInstanceOf(ApiError);
    expect(e.message).toBe('Rate limited, retry in 17s');
    expect(e.retryAfter).toBe(17);
  });
  it('400 -> Invalid ticker', async () => {
    expect((await toApiError(json(400, { detail: 'Invalid symbol.' }))).message).toBe('Invalid ticker');
  });
  it('other statuses surface detail', async () => {
    expect((await toApiError(json(404, { detail: "Company 'ZZZZ' not found on IDX." }))).message).toBe(
      "Company 'ZZZZ' not found on IDX.",
    );
    expect((await toApiError(new Response('oops', { status: 502 }))).message).toBe('Request failed (HTTP 502)');
  });
});

describe('display helpers', () => {
  it('maps backend color keys to neon hex', () => {
    expect(colorHex('green')).toBe('#00f5ff');
    expect(colorHex('yellow')).toBe('#e6ff00');
    expect(colorHex('amber')).toBe('#ffaa00');
    expect(colorHex('red')).toBe('#ff2d55');
  });
  it('thermal scale endpoints', () => {
    expect(thermalColor(0)).toBe('#ff2d55');
    expect(thermalColor(100)).toBe('#00f5ff');
    expect(thermalColor(-5)).toBe('#ff2d55');
  });
  it('momentum N/A quirk', () => {
    expect(isNoData('momentum', 10, 0.4)).toBe(true);
    expect(isNoData('momentum', 10, 1)).toBe(false);
    expect(isNoData('momentum', 10.5, 0.4)).toBe(false);
    expect(isNoData('valuation', 10, 0.4)).toBe(false);
  });
  it('bank detection', () => {
    expect(isFinancialSector('Financials')).toBe(true);
    expect(isFinancialSector('Banks')).toBe(true);
    expect(isFinancialSector('Energy')).toBe(false);
    expect(isFinancialSector(null)).toBe(false);
  });
  it('formats IDR and signed pct', () => {
    expect(formatIdr(6100)).toBe('Rp 6,100');
    expect(formatIdr(null)).toBe('Rp —');
    expect(formatSignedPct(2.345)).toBe('+2.3%');
    expect(formatSignedPct(-1)).toBe('-1.0%');
    expect(formatSignedPct(0)).toBe('±0.0%');
  });
});
