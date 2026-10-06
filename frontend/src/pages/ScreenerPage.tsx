import { useId, useMemo, useState } from 'react';
import type { Regime, Score, SubScoreKey } from '../api/types';
import { ErrorAlert, Scanning } from '../components/Status';
import { TickerRow } from '../components/TickerRow';
import { Tip } from '../components/Tip';
import { AllRegimesTipText, HEALTH_EXPLAINER, RegimeTipText } from '../components/explainers';
import { useScreen } from '../hooks/useScreen';
import { usePins } from '../hooks/usePins';
import { REGIMES, REGIME_COLOR_KEY, SUB_SCORE_KEYS, SUB_SCORE_META, colorHex } from '../theme/tokens';

const INDEX = 'LQ45';
const LIMIT = 50;

type SortKey = 'composite' | SubScoreKey;
const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'composite', label: 'Health score' },
  ...SUB_SCORE_KEYS.map((k) => ({ key: k, label: `${SUB_SCORE_META[k].short} · ${SUB_SCORE_META[k].label}` })),
];
const sortValue = (s: Score, key: SortKey) => (key === 'composite' ? s.composite : s.sub_scores[key]);

export function ScreenerPage({ onOpen }: { onOpen: (symbol: string) => void }) {
  const { data, error, loading, reload } = useScreen(INDEX, LIMIT);
  const [regimes, setRegimes] = useState<Set<Regime>>(new Set());
  const [sector, setSector] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [desc, setDesc] = useState(true);
  const [sortKey, setSortKey] = useState<SortKey>('composite');
  const sectorId = useId();
  const minId = useId();
  const sortId = useId();

  const sectors = useMemo(
    () => [...new Set((data?.results ?? []).map((r) => r.sector).filter((s): s is string => !!s))].sort(),
    [data],
  );

  const { isPinned } = usePins();

  const rows = useMemo(() => {
    const list = (data?.results ?? []).filter(
      (r) =>
        (regimes.size === 0 || regimes.has(r.regime)) &&
        (!sector || r.sector === sector) &&
        r.composite >= minScore,
    );
    const ranked = [...list]
      .sort((a, b) => {
        const d = sortValue(a, sortKey) - sortValue(b, sortKey);
        return (desc ? -d : d) || b.composite - a.composite;
      })
      .map((score, i) => ({ score, rank: i + 1, pinned: isPinned(score.symbol) }));
    return [...ranked.filter((r) => r.pinned), ...ranked.filter((r) => !r.pinned)];
  }, [data, regimes, sector, minScore, desc, sortKey, isPinned]);

  const toggleRegime = (r: Regime) =>
    setRegimes((prev) => {
      const next = new Set(prev);
      if (next.has(r)) next.delete(r);
      else next.add(r);
      return next;
    });

  const filtersActive = regimes.size > 0 || !!sector || minScore > 0;

  return (
    <div className="stack">
      <section className="panel" aria-label="Filters">
        <h2 className="panel-title">
          Screener // {INDEX} ·{' '}
          <Tip text="Stocks are sorted by their composite health score from 0 to 100. It is the sum of five sub-scores (valuation, momentum, debt, quality and profitability), each worth up to 20 points. Higher means stronger fundamentals.">
            ranked by health score
          </Tip>
        </h2>
        <div className="toolbar">
          <div className="field" role="group" aria-label="Filter by regime">
            <Tip text={<AllRegimesTipText />}>REGIME</Tip>
            {REGIMES.map((r) => (
              <Tip
                key={r}
                interactive
                text={<RegimeTipText regime={r} hint="Click to filter the list." />}
              >
                <button
                  type="button"
                  className="chip"
                  aria-pressed={regimes.has(r)}
                  style={{ ['--chip-color' as string]: colorHex(REGIME_COLOR_KEY[r]) }}
                  onClick={() => toggleRegime(r)}
                >
                  {r}
                </button>
              </Tip>
            ))}
          </div>

          <div className="field">
            <label htmlFor={sectorId}>SECTOR</label>
            <select id={sectorId} className="select" value={sector} onChange={(e) => setSector(e.target.value)}>
              <option value="">All sectors</option>
              {sectors.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor={minId}>MIN SCORE</label>
            <input
              id={minId}
              className="range"
              type="range"
              min={0}
              max={100}
              step={5}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
            />
            <output htmlFor={minId} className="mono" style={{ color: 'var(--text)', minWidth: 24 }}>
              {minScore}
            </output>
          </div>

          <div className="field sort-field">
            <label htmlFor={sortId}>SORT BY</label>
            <select
              id={sortId}
              className="select"
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.key} value={o.key}>
                  {o.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              className="btn btn-ghost sort-dir"
              onClick={() => setDesc((d) => !d)}
              aria-label={`Sort order, currently ${desc ? 'highest first' : 'lowest first'}`}
            >
              {desc ? '▼ High → Low' : '▲ Low → High'}
            </button>
          </div>

          {filtersActive && (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setRegimes(new Set());
                setSector('');
                setMinScore(0);
              }}
            >
              Reset
            </button>
          )}
        </div>
      </section>

      {loading && <Scanning label={`SCANNING ${INDEX}...`} />}
      {error != null && !loading && <ErrorAlert error={error} onRetry={reload} />}

      {data && !loading && (
        <section aria-label="Ranked stocks">
          <p className="dim mono" style={{ fontSize: 11, margin: '0 0 6px' }} aria-live="polite">
            {filtersActive
              ? `Showing ${rows.length} of ${data.count} stocks`
              : `Showing ${data.count} stocks`}
          </p>
          <div className="list-header">
            <span aria-hidden="true">#</span>
            <span aria-hidden="true">TICKER</span>
            <span aria-hidden="true">COMPANY</span>
            <span>
              <Tip text={<AllRegimesTipText />}>REGIME</Tip>
            </span>
            <span>
              <Tip text={HEALTH_EXPLAINER}>HEALTH</Tip>
            </span>
            <span aria-hidden="true">VAL · MOM · DEBT · QUAL · PROF</span>
          </div>
          {rows.length === 0 ? (
            <p className="empty">&gt; NO MATCHES. Loosen the filters.</p>
          ) : (
            <ol className="ticker-list">
              {rows.map((r, i) => (
                <li
                  key={r.score.symbol}
                  className={[
                    r.pinned ? 'is-pinned' : '',
                    r.pinned && !rows[i + 1]?.pinned && i < rows.length - 1 ? 'pinned-last' : '',
                  ]
                    .filter(Boolean)
                    .join(' ') || undefined}
                >
                  <TickerRow rank={r.rank} score={r.score} onOpen={onOpen} />
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
