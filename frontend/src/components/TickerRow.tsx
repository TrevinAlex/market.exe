import type { Score } from '../api/types';
import { baseTicker } from '../api/client';
import { colorHex } from '../theme/tokens';
import { HealthBar } from './HealthBar';
import { RegimeBadge } from './RegimeBadge';
import { SubScoreDots } from './SubScoreDots';

interface Props {
  rank: number;
  score: Score;
  onOpen: (symbol: string) => void;
}

/**
 * One screener line. The whole row is clickable with the mouse; the ticker
 * button is the keyboard entry point (so the focusable dot tooltips are not
 * nested inside another interactive element).
 */
export function TickerRow({ rank, score, onOpen }: Props) {
  const sym = baseTicker(score.symbol);
  const open = () => onOpen(sym);

  return (
    <div
      className="ticker-row"
      style={{ ['--regime' as string]: colorHex(score.color) }}
      onClick={open}
    >
      <span className="rank">#{rank}</span>
      <button
        type="button"
        className="sym"
        style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left' }}
        onClick={(e) => {
          e.stopPropagation();
          open();
        }}
        aria-label={`Open ${sym}, ${score.company_name}`}
      >
        {sym}
      </button>
      <span className="name" title={score.company_name}>
        {score.company_name}
        <small>{score.sub_sector ?? score.sector ?? '—'}</small>
      </span>
      <RegimeBadge regime={score.regime} color={score.color} />
      <HealthBar score={score.composite} regime={score.regime} color={score.color} confidence={score.confidence} />
      <SubScoreDots
        subScores={score.sub_scores}
        normalized={score.sub_scores_normalized}
        confidence={score.confidence}
        sector={score.sector}
      />
    </div>
  );
}
