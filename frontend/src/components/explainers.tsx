import type { Regime } from '../api/types';
import { REGIMES, REGIME_MEANING, REGIME_RANGE } from '../theme/tokens';

export const HEALTH_EXPLAINER =
  "A 0–100 score of the company's financial health, shown like a game HP bar. It is the sum of five " +
  'sub-scores worth up to 20 points each: valuation, momentum, debt, quality and profitability. ' +
  'The marks at 30, 50 and 70 are where the regime changes. A faded bar means some of the data was missing.';

export function RegimeTipText({ regime, hint }: { regime: Regime; hint?: string }) {
  return (
    <>
      <b>{regime}</b> · health score {REGIME_RANGE[regime]}
      <br />
      {REGIME_MEANING[regime]}
      {hint && (
        <>
          <br />
          <span className="dim">{hint}</span>
        </>
      )}
    </>
  );
}

export function AllRegimesTipText() {
  return (
    <>
      The market phase the stock appears to be in, decided by its health score:
      <span className="tip-list">
        {REGIMES.map((r) => (
          <span key={r}>
            <b>{r}</b> ({REGIME_RANGE[r]}): {REGIME_MEANING[r]}
          </span>
        ))}
      </span>
    </>
  );
}
