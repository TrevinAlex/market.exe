import { describe, expect, it } from 'vitest';
import { exitLiquidity, formatIdrCompact, formatRupiahInput, parseRupiah, positionRisk } from './components/positionRisk';

describe('formatRupiahInput', () => {
  it.each([
    ['10000000', '10.000.000'],
    ['1000', '1.000'],
    ['999', '999'],
    ['10.000.000.00', '1.000.000.000'],
    ['10.0000', '100.000'],
    ['007', '7'],
    ['', ''],
    ['Rp 5000000', '5.000.000'],
    ['10jt', '10jt'],
    ['1,5 jt', '1,5 jt'],
  ])('%j -> %j', (raw, out) => expect(formatRupiahInput(raw).text).toBe(out));

  it('keeps the caret after the same digit', () => {
    expect(formatRupiahInput('1.0000', 6)).toEqual({ text: '10.000', caret: 6 });
    expect(formatRupiahInput('.000.000', 0)).toEqual({ text: '0', caret: 0 });
    expect(formatRupiahInput('15.000', 2)).toEqual({ text: '15.000', caret: 2 });
  });
});

const bands = { p10: 9000, p25: 9500, p50: 10000, p75: 10500, p90: 11200 };

describe('positionRisk', () => {
  it('scales the amount by each band', () => {
    const r = positionRisk(10_000_000, 10_000, bands)!;
    expect(r.lots).toBe(10);
    const [bad, mid, good] = r.outcomes;
    expect(bad).toMatchObject({ key: 'p10', value: 9_000_000, change: -1_000_000 });
    expect(bad.changePct).toBeCloseTo(-10);
    expect(mid.change).toBe(0);
    expect(good.value).toBeCloseTo(11_200_000);
  });

  it('rejects empty or invalid input', () => {
    expect(positionRisk(0, 10_000, bands)).toBeNull();
    expect(positionRisk(1_000, 0, bands)).toBeNull();
  });
});

describe('parseRupiah', () => {
  it.each([
    ['10000000', 10_000_000],
    ['10.000.000', 10_000_000],
    ['10,000,000', 10_000_000],
    ['Rp 5.000.000', 5_000_000],
    ['10jt', 10_000_000],
    ['1,5 jt', 1_500_000],
    ['1.5m', 1_500_000],
    ['500rb', 500_000],
    ['2 miliar', 2_000_000_000],
  ])('%s -> %d', (text, value) => expect(parseRupiah(text)).toBe(value));

  it.each(['', 'abc', '0', '-5', '1.2.3jt'])('rejects %j', (text) => expect(parseRupiah(text)).toBeNull());
});

describe('formatIdrCompact', () => {
  it('formats money compactly with a true minus sign', () => {
    expect(formatIdrCompact(-1_234_000)).toBe('−Rp 1.2M');
    expect(formatIdrCompact(850_000, true)).toBe('+Rp 850K');
    expect(formatIdrCompact(10_000_000)).toBe('Rp 10M');
    expect(formatIdrCompact(0, true)).toBe('Rp 0');
  });
});

describe('exitLiquidity', () => {
  it('uses the square-root impact rule', () => {
    const r = exitLiquidity(4_000_000_000, 100_000_000_000, 0.02)!;
    expect(r.shareOfDay).toBeCloseTo(0.04);
    expect(r.costPct).toBeCloseTo(0.4);
    expect(r.cost).toBeCloseTo(16_000_000);
    expect(r.daysToExit).toBe(1);
    expect(r.level).toBe('noticeable');
  });

  it('grades size against daily trading', () => {
    expect(exitLiquidity(10_000_000, 100_000_000_000, 0.02)!.level).toBe('easy');
    const big = exitLiquidity(50_000_000_000, 100_000_000_000, 0.02)!;
    expect(big.level).toBe('hard');
    expect(big.daysToExit).toBe(3);
  });

  it('a wilder market costs more to exit', () => {
    const calm = exitLiquidity(1e9, 1e11, 0.01)!;
    const panic = exitLiquidity(1e9, 1e11, 0.02)!;
    expect(panic.costPct).toBeCloseTo(calm.costPct * 2);
  });

  it('returns null without data', () => {
    expect(exitLiquidity(1e9, 0, 0.02)).toBeNull();
    expect(exitLiquidity(0, 1e11, 0.02)).toBeNull();
    expect(exitLiquidity(1e9, 1e11, 0)).toBeNull();
  });
});
