import { useId } from 'react';
import type { Bands, SimEvent } from '../api/types';
import { palette } from '../theme/tokens';
import { formatIdr } from '../theme/format';

type DailyBands = Record<keyof Bands, number[]>;

interface Props {
  paths: number[][];
  bands: Bands;
  /** Per-day percentiles from the backend. Estimated from `paths` when missing. */
  dailyBands?: DailyBands;
  events?: SimEvent[];
  currentPrice: number;
  horizonDays: number;
}

const W = 760;
const H = 320;
const M = { top: 22, right: 132, bottom: 30, left: 76 };
const KEYS = ['p10', 'p25', 'p50', 'p75', 'p90'] as const;

/**
 * Fan chart: the P10–P90 (light) and P25–P75 (dark) ranges as shaded bands that
 * widen over the horizon, the median as one bright line, a few faint sample paths
 * for texture, the current price as a dashed baseline, and ex-dividend markers.
 */
export function FanChart({ paths, bands, dailyBands, events = [], currentPrice, horizonDays }: Props) {
  const titleId = useId();
  const descId = useId();

  const db = dailyBands && dailyBands.p50?.length > 1 ? dailyBands : bandsFromPaths(paths, currentPrice, horizonDays);
  const days = Math.max(1, db.p50.length - 1);
  const shown = paths.slice(0, 12); // a few paths for texture; the bands carry the forecast

  // Scale to the bands (plus the shown paths), so a single extreme path can't squash the chart.
  const values = [currentPrice, ...db.p10, ...db.p90, ...shown.flat()].filter(Number.isFinite);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (hi - lo < 1e-9) {
    lo -= 1;
    hi += 1;
  }
  const pad = (hi - lo) * 0.06;
  lo -= pad;
  hi += pad;

  const plotW = W - M.left - M.right;
  const plotH = H - M.top - M.bottom;
  const x = (d: number) => M.left + (d / days) * plotW;
  const y = (v: number) => M.top + (1 - (Math.min(hi, Math.max(lo, v)) - lo) / (hi - lo)) * plotH;

  const yTicks = niceTicks(lo, hi, 5);
  const xTicks = dayTicks(days);
  const labelX = x(days) + 10;

  const line = (vals: number[]) => vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const area = (upper: number[], lower: number[]) =>
    `${line(upper)} ${lower
      .map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .reverse()
      .join(' ')}`;

  const divs = events.filter((e) => e.type === 'dividend' && e.day >= 1 && e.day <= days);

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={`${titleId} ${descId}`}>
        <title id={titleId}>Simulated price range over {days} trading days</title>
        <desc id={descId}>
          {`Start ${formatIdr(currentPrice)}. Final-day range: p10 ${formatIdr(bands.p10)}, p25 ${formatIdr(
            bands.p25,
          )}, median ${formatIdr(bands.p50)}, p75 ${formatIdr(bands.p75)}, p90 ${formatIdr(bands.p90)}.`}
          {divs.map((e) => ` Ex-dividend Rp ${e.amount} on trading day ${e.day}.`).join('')}
        </desc>

        {/* grid + y axis */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={M.left} x2={x(days)} y1={y(t)} y2={y(t)} stroke={palette.border} strokeWidth={1} />
            <text
              x={M.left - 8}
              y={y(t)}
              textAnchor="end"
              dominantBaseline="middle"
              fill={palette.dim}
              fontSize={10}
              fontFamily="var(--font-mono)"
            >
              {formatIdr(t).replace('Rp ', '')}
            </text>
          </g>
        ))}
        {xTicks.map((d) => (
          <text
            key={d}
            x={x(d)}
            y={H - M.bottom + 16}
            textAnchor="middle"
            fill={palette.dim}
            fontSize={10}
            fontFamily="var(--font-mono)"
          >
            {d === 0 ? 'T0' : `D+${d}`}
          </text>
        ))}
        <line x1={M.left} x2={x(days)} y1={H - M.bottom} y2={H - M.bottom} stroke={palette.border} />

        {/* shaded ranges */}
        <polygon points={area(db.p90, db.p10)} fill={palette.cyan} fillOpacity={0.1} />
        <polygon points={area(db.p75, db.p25)} fill={palette.cyan} fillOpacity={0.22} />
        <polyline points={line(db.p90)} fill="none" stroke={palette.cyan} strokeOpacity={0.35} strokeWidth={1} />
        <polyline points={line(db.p10)} fill="none" stroke={palette.cyan} strokeOpacity={0.35} strokeWidth={1} />

        {/* a few sample paths for texture */}
        <g fill="none" stroke={palette.text} strokeWidth={1} strokeOpacity={0.12}>
          {shown.map((p, i) => (
            <polyline key={i} points={line(p)} />
          ))}
        </g>

        {/* current price baseline */}
        <line
          x1={M.left}
          x2={x(days)}
          y1={y(currentPrice)}
          y2={y(currentPrice)}
          stroke={palette.text}
          strokeOpacity={0.6}
          strokeDasharray="5 4"
        />

        {/* median */}
        <polyline
          points={line(db.p50)}
          fill="none"
          stroke={palette.cyan}
          strokeWidth={2}
          style={{ filter: 'none' }}
        />

        {/* ex-dividend markers */}
        {divs.map((e) => (
          <g key={`div-${e.day}`}>
            <line
              x1={x(e.day)}
              x2={x(e.day)}
              y1={M.top}
              y2={H - M.bottom}
              stroke={palette.amber}
              strokeOpacity={0.8}
              strokeDasharray="3 3"
            />
            <text
              x={x(e.day)}
              y={M.top - 8}
              textAnchor="middle"
              fontSize={10}
              fontFamily="var(--font-mono)"
              fill={palette.amber}
            >
              EX-DIV Rp {formatIdr(e.amount).replace('Rp ', '')}
            </text>
          </g>
        ))}

        {/* end-of-horizon labels (de-overlapped) */}
        {bandLabels(bands, currentPrice, y).map((l) => (
          <text
            key={l.key}
            x={labelX}
            y={l.y}
            dominantBaseline="middle"
            fontSize={10}
            fontFamily="var(--font-mono)"
            fill={l.key === 'NOW' ? palette.text : palette.cyan}
            fillOpacity={l.key === 'p50' || l.key === 'NOW' ? 1 : 0.75}
          >
            {l.key.toUpperCase()} {formatIdr(l.value).replace('Rp ', '')}
          </text>
        ))}
      </svg>
      <div className="fan-legend mono" aria-hidden="true">
        <span>
          <i className="sw sw-outer" /> 80% range (P10–P90)
        </span>
        <span>
          <i className="sw sw-inner" /> 50% range (P25–P75)
        </span>
        <span>
          <i className="sw sw-median" /> median
        </span>
        <span>
          <i className="sw sw-now" /> today's price
        </span>
        {divs.length > 0 && (
          <span>
            <i className="sw sw-div" /> ex-dividend
          </span>
        )}
      </div>
    </div>
  );
}

/** Fallback for older responses: per-day percentiles of the sample paths. */
export function bandsFromPaths(paths: number[][], current: number, horizon: number): DailyBands {
  const days = Math.max(1, horizon, ...paths.map((p) => p.length - 1));
  const out = { p10: [], p25: [], p50: [], p75: [], p90: [] } as DailyBands;
  for (let d = 0; d <= days; d++) {
    const col = paths.map((p) => p[d]).filter(Number.isFinite).sort((a, b) => a - b);
    for (const k of KEYS) out[k].push(col.length ? quantile(col, Number(k.slice(1)) / 100) : current);
  }
  return out;
}

function quantile(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q;
  const i = Math.floor(pos);
  return sorted[i] + (sorted[Math.min(i + 1, sorted.length - 1)] - sorted[i]) * (pos - i);
}

function bandLabels(bands: Bands, current: number, y: (v: number) => number) {
  const items = [
    { key: 'p90', value: bands.p90 },
    { key: 'p75', value: bands.p75 },
    { key: 'p50', value: bands.p50 },
    { key: 'p25', value: bands.p25 },
    { key: 'p10', value: bands.p10 },
    { key: 'NOW', value: current },
  ]
    .map((i) => ({ ...i, y: y(i.value) }))
    .sort((a, b) => a.y - b.y);
  const gap = 12;
  for (let i = 1; i < items.length; i++) {
    if (items[i].y - items[i - 1].y < gap) items[i].y = items[i - 1].y + gap;
  }
  return items;
}

function niceTicks(lo: number, hi: number, count: number): number[] {
  const raw = (hi - lo) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

function dayTicks(days: number): number[] {
  const step = days <= 10 ? 1 : days <= 30 ? 5 : days <= 60 ? 10 : 20;
  const out: number[] = [];
  for (let d = 0; d <= days; d += step) out.push(d);
  if (out[out.length - 1] !== days) out.push(days);
  return out;
}
