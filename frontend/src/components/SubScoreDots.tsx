import { useId, useState } from 'react';
import type { SubScoreKey, SubScores } from '../api/types';
import { SUB_SCORE_KEYS, SUB_SCORE_META, isFinancialSector } from '../theme/tokens';
import { isNoData, normalizedOf } from './subScoreUtils';

interface Props {
  subScores: SubScores;
  normalized: Record<string, number>;
  confidence: number;
  sector: string | null;
}

/** Row of five ●●●○○ meters, one per dimension, each with a hover/focus tooltip. */
export function SubScoreDots({ subScores, normalized, confidence, sector }: Props) {
  return (
    <div className="dots-group" role="list" aria-label="Sub-scores">
      {SUB_SCORE_KEYS.map((k) => (
        <DotMeter
          key={k}
          dim={k}
          value={subScores[k]}
          norm={normalizedOf(k, subScores, normalized)}
          noData={isNoData(k, subScores[k], confidence)}
          bankNote={k === 'debt' && isFinancialSector(sector)}
        />
      ))}
    </div>
  );
}

interface DotProps {
  dim: SubScoreKey;
  value: number;
  norm: number;
  noData: boolean;
  bankNote: boolean;
}

function DotMeter({ dim, value, norm, noData, bankNote }: DotProps) {
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const meta = SUB_SCORE_META[dim];
  const filled = Math.max(0, Math.min(5, Math.round(norm * 5)));

  const summary = noData
    ? `${meta.label}: N/A, no data`
    : `${meta.label}: ${filled} of 5, ${value.toFixed(2)} of 20`;

  return (
    <span
      role="listitem"
      className={`dots${noData ? ' na' : ''}`}
      tabIndex={0}
      aria-label={summary}
      aria-describedby={open ? tipId : undefined}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
      // Tooltip interaction should not trigger the parent row's click.
      onClick={(e) => e.stopPropagation()}
    >
      <span className="dots-label" aria-hidden="true">
        {meta.short}
        {bankNote && <i className="info-icon">i</i>}
      </span>
      <span className="dots-row" aria-hidden="true">
        {noData ? (
          '·····'
        ) : (
          <>
            {'●'.repeat(filled)}
            <span className="off">{'○'.repeat(5 - filled)}</span>
          </>
        )}
      </span>
      {open && (
        <span role="tooltip" id={tipId} className="tooltip">
          <strong>{meta.label}</strong>
          <br />
          {noData ? (
            <>N/A: no data for this dimension. Neutral placeholder (10 / 20) used.</>
          ) : (
            <>
              {value.toFixed(2)} / 20 ({Math.round(norm * 100)}%)
            </>
          )}
          <br />
          <span className="dim">{meta.measures}. High = {meta.high.toLowerCase()}.</span>
          {bankNote && (
            <>
              <br />
              <span style={{ color: 'var(--amber)' }}>ⓘ Leverage is structurally high for banks.</span>
            </>
          )}
        </span>
      )}
    </span>
  );
}
