import type { SubScores } from '../api/types';
import { SUB_SCORE_KEYS, SUB_SCORE_META, palette } from '../theme/tokens';
import { isNoData, normalizedOf } from './subScoreUtils';

interface Props {
  subScores: SubScores;
  normalized: Record<string, number>;
  confidence: number;
  size?: number;
}

/** Pentagon radar of the 5 normalised sub-scores (plain SVG). */
export function RadarChart({ subScores, normalized, confidence, size = 260 }: Props) {
  const c = size / 2;
  const r = size / 2 - 44;
  const n = SUB_SCORE_KEYS.length;
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const pt = (i: number, v: number) => [c + Math.cos(angle(i)) * r * v, c + Math.sin(angle(i)) * r * v] as const;
  const ring = (v: number) => SUB_SCORE_KEYS.map((_, i) => pt(i, v).join(',')).join(' ');

  const values = SUB_SCORE_KEYS.map((k) => normalizedOf(k, subScores, normalized));
  const shape = values.map((v, i) => pt(i, Math.max(0.02, v)).join(',')).join(' ');
  const label = SUB_SCORE_KEYS.map((k, i) => `${SUB_SCORE_META[k].label} ${Math.round(values[i] * 100)}%`).join(', ');

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width="100%" style={{ maxWidth: size }} role="img" aria-label={`Sub-score radar: ${label}`}>
      {[0.25, 0.5, 0.75, 1].map((v) => (
        <polygon key={v} points={ring(v)} fill="none" stroke={palette.border} strokeWidth={1} />
      ))}
      {SUB_SCORE_KEYS.map((_, i) => {
        const [x, y] = pt(i, 1);
        return <line key={i} x1={c} y1={c} x2={x} y2={y} stroke={palette.border} />;
      })}
      <polygon
        points={shape}
        fill={palette.cyan}
        fillOpacity={0.18}
        stroke={palette.cyan}
        strokeWidth={1.5}
        style={{ filter: 'drop-shadow(0 0 4px rgba(0,245,255,0.7))' }}
      />
      {SUB_SCORE_KEYS.map((k, i) => {
        const na = isNoData(k, subScores[k], confidence);
        const [px, py] = pt(i, Math.max(0.02, values[i]));
        const [lx, ly] = pt(i, 1.22);
        return (
          <g key={k}>
            <circle cx={px} cy={py} r={3} fill={na ? palette.grey : palette.cyan} />
            <text
              x={lx}
              y={ly}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize={10}
              fontFamily="var(--font-mono)"
              fill={na ? palette.grey : palette.dim}
            >
              {SUB_SCORE_META[k].short}
              {na ? ' N/A' : ` ${Math.round(values[i] * 100)}`}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
