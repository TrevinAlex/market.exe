import { describe, expect, it } from 'vitest';
import { formatIdrCompact, parseRupiah, positionRisk } from './components/positionRisk';

const bands = { p10: 9000, p25: 9500, p50: 10000, p75: 10500, p90: 11200 };

describe('positionRisk', () => {
  it('scales the amount by each band', () => {
    const r = positionRisk(10_000_000, 10_000, bands)!;
    expect(r.lots).toBe(10); // 10M / (10,000 × 100)
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
