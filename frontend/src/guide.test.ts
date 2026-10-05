import { describe, expect, it } from 'vitest';
import { GLOSSARY, REPORT_CARD, filterGlossary } from './content/guide';
import { REGIMES, SUB_SCORE_META } from './theme/tokens';

const allTerms = GLOSSARY.flatMap((g) => g.entries.map((e) => e.term));

describe('report card content', () => {
  it('has unique glossary terms', () => {
    expect(new Set(allTerms).size).toBe(allTerms.length);
  });

  it('explains every regime, sub-score and simulation stat shown in the app', () => {
    for (const r of REGIMES) expect(allTerms).toContain(r);
    for (const m of Object.values(SUB_SCORE_META)) expect(allTerms).toContain(m.label);
    for (const t of ['Health score', 'Probability up', 'Expected return', 'Bearish (P10)', 'Median (P50)', 'Bullish (P90)', 'Data coverage', 'Daily volatility'])
      expect(allTerms).toContain(t);
  });

  it('grades every report row', () => {
    for (const r of REPORT_CARD) expect(['pass', 'warn', 'fail']).toContain(r.grade);
  });

  it('filters by term or text, case-insensitively', () => {
    const hits = filterGlossary(GLOSSARY, 'PROBABILITY').flatMap((g) => g.entries.map((e) => e.term));
    expect(hits).toContain('Probability up');
    expect(filterGlossary(GLOSSARY, '')).toBe(GLOSSARY);
    expect(filterGlossary(GLOSSARY, 'zzzz-no-match')).toEqual([]);
  });
});
