import type { Regime, SectorRegime } from '../api/types';
import { REGIMES, REGIME_COLOR_KEY, colorHex, thermalColor } from '../theme/tokens';

export const SECTOR_STRESS_PCT = 50;

export function SectorHeatmap({ sectors }: { sectors: SectorRegime[] }) {
  return (
    <ul className="heat-grid" style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {sectors.map((s) => (
        <li key={s.sector}>
          <SectorTile s={s} />
        </li>
      ))}
    </ul>
  );
}

function SectorTile({ s }: { s: SectorRegime }) {
  const heat = thermalColor(s.avg_score);
  const regimes = REGIMES.filter((r) => (s.distribution[r] ?? 0) > 0);
  const breakdown = REGIMES.map((r) => `${s.distribution[r] ?? 0} ${r}`).join(', ');
  const stressed = s.stressed_pct >= SECTOR_STRESS_PCT;

  return (
    <article
      className="heat-tile"
      style={{ ['--heat' as string]: heat, height: '100%' }}
      aria-label={`${s.sector}: average score ${s.avg_score.toFixed(1)}, ${s.stressed_pct.toFixed(
        0,
      )}% stressed, ${s.total} stocks (${breakdown})`}
    >
      <div className="heat-meta heat-head">
        <h3>{s.sector}</h3>
        <span className="heat-count">{s.total} stocks</span>
      </div>

      <div className="heat-big" aria-hidden="true">
        {s.stressed_pct.toFixed(0)}%<small>stressed{stressed ? ' ▲' : ''}</small>
      </div>

      <div className="heat-meta heat-score" aria-hidden="true">
        <span>Avg. score</span>
        <span className="mono" style={{ color: heat }}>
          {s.avg_score.toFixed(1)} <span className="dim">/ 100</span>
        </span>
      </div>

      <div className="stackbar" aria-hidden="true">
        {regimes.map((r) => (
          <span
            key={r}
            title={`${r}: ${s.distribution[r]}`}
            style={{
              width: `${((s.distribution[r] ?? 0) / Math.max(1, s.total)) * 100}%`,
              background: colorHex(REGIME_COLOR_KEY[r as Regime]),
            }}
          />
        ))}
      </div>
      <ul className="legend heat-legend" aria-hidden="true">
        {regimes.map((r) => (
          <li key={r}>
            <i style={{ background: colorHex(REGIME_COLOR_KEY[r]) }} />
            {r} <b>{s.distribution[r]}</b>
          </li>
        ))}
      </ul>
    </article>
  );
}
