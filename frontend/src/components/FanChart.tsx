import { useId } from 'react';
import type { Bands } from '../api/types';
import { palette } from '../theme/tokens';
import { formatIdr } from '../theme/format';

interface Props {
  paths: number[][];
  bands: Bands;
  currentPrice: number;
  horizonDays: number;
}

const W = 760;
const H = 320;
const M = { top: 16, right: 132, bottom: 30, left: 76 };
const BAND_W = 26;

/**
 * Fan chart: sample paths as faint cyan lines, the p10–p90 / p25–p75 ranges as
 * shaded bands at the horizon, and the current price as a dashed baseline.
 */
export function FanChart({ paths, bands, currentPrice, horizonDays }: Props) {
  const titleId = useId();
  const descId = useId();

  const days = Math.max(1, horizonDays, ...paths.map((p) => p.length - 1));
  const values = [currentPrice, bands.p10, bands.p90, ...paths.flat()].filter(Number.isFinite);
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
  const y = (v: number) => M.top + (1 - (v - lo) / (hi - lo)) * plotH;

  const yTicks = niceTicks(lo, hi, 5);
  const xTicks = dayTicks(days);
  const bandX = x(days) + 8;

  const toPoints = (p: number[]) => p.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={`${titleId} ${descId}`}>
        <title id={titleId}>Simulated price paths over {days} days</title>
        <desc id={descId}>
          {`Start ${formatIdr(currentPrice)}. Final-day range: p10 ${formatIdr(bands.p10)}, p25 ${formatIdr(
            bands.p25,
          )}, median ${formatIdr(bands.p50)}, p75 ${formatIdr(bands.p75)}, p90 ${formatIdr(bands.p90)}.`}
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
        {/* x axis */}
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

        {/* horizon guide */}
        <line x1={x(days)} x2={x(days)} y1={M.top} y2={H - M.bottom} stroke={palette.border} strokeDasharray="2 3" />

        {/* sample paths */}
        <g fill="none" stroke={palette.cyan} strokeWidth={1} strokeOpacity={0.16}>
          {paths.map((p, i) => (
            <polyline key={i} points={toPoints(p)} />
          ))}
        </g>

        {/* current price baseline */}
        <line
          x1={M.left}
          x2={bandX + BAND_W}
          y1={y(currentPrice)}
          y2={y(currentPrice)}
          stroke={palette.text}
          strokeOpacity={0.7}
          strokeDasharray="5 4"
        />

        {/* horizon bands */}
        <rect
          x={bandX}
          width={BAND_W}
          y={y(bands.p90)}
          height={Math.max(1, y(bands.p10) - y(bands.p90))}
          fill={palette.cyan}
          fillOpacity={0.15}
          stroke={palette.cyan}
          strokeOpacity={0.35}
        />
        <rect
          x={bandX}
          width={BAND_W}
          y={y(bands.p75)}
          height={Math.max(1, y(bands.p25) - y(bands.p75))}
          fill={palette.cyan}
          fillOpacity={0.38}
        />
        <line
          x1={bandX - 3}
          x2={bandX + BAND_W + 3}
          y1={y(bands.p50)}
          y2={y(bands.p50)}
          stroke={palette.cyan}
          strokeWidth={2}
          style={{ filter: 'drop-shadow(0 0 3px #00f5ff)' }}
        />

        {/* band labels (de-overlapped) */}
        {bandLabels(bands, currentPrice, y).map((l) => (
          <text
            key={l.key}
            x={bandX + BAND_W + 8}
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
    </div>
  );
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
