import type { Regime } from '../api/types';
import { LOW_SIGNAL_THRESHOLD, REGIME_COLOR_KEY, REGIME_TICKS, colorHex } from '../theme/tokens';

interface Props {
  score: number;
  regime: Regime | string;
  confidence: number;
  color?: string;
  size?: 'sm' | 'lg';
  showTickLabels?: boolean;
}

export function HealthBar({
  score,
  regime,
  confidence,
  color,
  size = 'sm',
  showTickLabels = size === 'lg',
}: Props) {
  const pct = Math.max(0, Math.min(100, score));
  const hex = colorHex(color ?? REGIME_COLOR_KEY[regime as Regime]);
  const critical = pct < 30;
  const lowSignal = confidence < LOW_SIGNAL_THRESHOLD;
  const fillOpacity = 0.4 + 0.6 * Math.max(0, Math.min(1, confidence));

  const classes = ['hp', size === 'lg' ? 'lg' : '', critical ? 'critical' : ''].join(' ').trim();

  return (
    <div className={classes} style={{ ['--regime' as string]: hex }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          className="hp-track"
          role="meter"
          aria-label="Health score"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Number(pct.toFixed(1))}
          aria-valuetext={`${pct.toFixed(1)} out of 100, ${regime}${critical ? ', critical' : ''}${
            lowSignal ? `, low signal (${Math.round(confidence * 100)}% data coverage)` : ''
          }`}
        >
          <div className="hp-fill" style={{ width: `${pct}%`, opacity: critical ? undefined : fillOpacity }} />
          {REGIME_TICKS.map((t) => (
            <span key={t} className="hp-tick" style={{ left: `${t}%` }} aria-hidden="true" />
          ))}
        </div>
        {showTickLabels && (
          <div className="hp-ticks-row" aria-hidden="true">
            {REGIME_TICKS.map((t) => (
              <span key={t} className="hp-tick-label" style={{ left: `${t}%`, top: 2 }}>
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
      <span className="hp-value" aria-hidden="true">
        <b>{pct.toFixed(1)}</b> / 100
      </span>
      <span className="hp-tag-slot">
        {lowSignal && (
          <span
            className="tag-low"
            title={`Only ${Math.round(confidence * 100)}% of the 5 dimensions had real data`}
          >
            LOW SIGNAL
          </span>
        )}
      </span>
    </div>
  );
}
