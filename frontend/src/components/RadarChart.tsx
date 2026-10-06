import { useId } from 'react';
import type { SubScores } from '../api/types';
import { SUB_SCORE_KEYS, SUB_SCORE_META, palette, thermalColor } from '../theme/tokens';
import { isNoData, normalizedOf } from './subScoreUtils';
import { Tip } from './Tip';

interface Props {
  subScores: SubScores;
  normalized: Record<string, number>;
  confidence: number;
  size?: number;
}

export function RadarChart({ subScores, normalized, confidence, size = 260 }: Props) {
  const gradId = useId();
  const c = size / 2;
  const r = size / 2 - 80;
  const n = SUB_SCORE_KEYS.length;
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const pt = (i: number, v: number) => [c + Math.cos(angle(i)) * r * v, c + Math.sin(angle(i)) * r * v] as const;
  const ring = (v: number) => SUB_SCORE_KEYS.map((_, i) => pt(i, v).join(',')).join(' ');

  const values = SUB_SCORE_KEYS.map((k) => normalizedOf(k, subScores, normalized));
  const shape = values.map((v, i) => pt(i, Math.max(0.02, v)).join(',')).join(' ');
  const label = SUB_SCORE_KEYS.map((k, i) => `${SUB_SCORE_META[k].label} ${Math.round(values[i] * 100)}%`).join(', ');

  const chart = (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width="100%"
      style={{ display: 'block' }}
      role="img"
      aria-label={`Sub-score radar: ${label}`}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={palette.cyan} stopOpacity={0.45} />
          <stop offset="100%" stopColor={palette.yellow} stopOpacity={0.25} />
        </linearGradient>
      </defs>

      {[1, 0.75, 0.5, 0.25].map((v, idx) => (
        <polygon
          key={v}
          points={ring(v)}
          fill="#ffffff"
          fillOpacity={idx % 2 === 0 ? 0.025 : 0.045}
          stroke="#ffffff"
          strokeOpacity={0.07}
          strokeWidth={1}
          strokeLinejoin="round"
        />
      ))}
      {SUB_SCORE_KEYS.map((_, i) => {
        const [x, y] = pt(i, 1);
        return <line key={i} x1={c} y1={c} x2={x} y2={y} stroke="#ffffff" strokeOpacity={0.06} />;
      })}

      {[0.5, 1].map((v) => {
        const [, y] = pt(0, v);
        return (
          <text
            key={v}
            x={c + 4}
            y={y + 10}
            fontSize={9}
            fontFamily="var(--font-sans)"
            fill={palette.grey}
            fillOpacity={0.8}
          >
            {v * 100}
          </text>
        );
      })}

      <polygon
        points={shape}
        fill={`url(#${gradId})`}
        stroke={palette.cyan}
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {SUB_SCORE_KEYS.map((k, i) => {
        const na = isNoData(k, subScores[k], confidence);
        const [px, py] = pt(i, Math.max(0.02, values[i]));
        return (
          <circle
            key={k}
            cx={px}
            cy={py}
            r={4.5}
            fill={na ? palette.grey : palette.cyan}
            stroke={palette.panel}
            strokeWidth={2}
          />
        );
      })}
    </svg>
  );

  return (
    <div className="radar" style={{ maxWidth: size }}>
      {chart}
      {SUB_SCORE_KEYS.map((k, i) => {
        const na = isNoData(k, subScores[k], confidence);
        const pct = Math.round(values[i] * 100);
        const [lx, ly] = pt(i, 1.3);
        const valueColor = na ? palette.grey : thermalColor(pct);
        return (
          <div
            key={k}
            className="radar-label"
            style={{ left: `${(lx / size) * 100}%`, top: `${(ly / size) * 100}%` }}
          >
            <Tip text={SUB_SCORE_META[k].measures} align={lx > c + 10 ? 'right' : 'left'}>
              {SUB_SCORE_META[k].label}
            </Tip>
            <span className="radar-value" style={{ color: valueColor }} aria-hidden="true">
              {na ? 'N/A' : pct}
            </span>
          </div>
        );
      })}
    </div>
  );
}
