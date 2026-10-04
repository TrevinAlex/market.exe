import { useId, useMemo, useState } from 'react';
import type { Regime } from '../api/types';
import { ErrorAlert, Scanning } from '../components/Status';
import { TickerRow } from '../components/TickerRow';
import { useScreen } from '../hooks/useScreen';
import { REGIMES, REGIME_COLOR_KEY, colorHex } from '../theme/tokens';

const INDEX = 'LQ45';
const LIMIT = 20;

export function ScreenerPage({ onOpen }: { onOpen: (symbol: string) => void }) {
  const { data, error, loading, reload } = useScreen(INDEX, LIMIT);
  const [regimes, setRegimes] = useState<Set<Regime>>(new Set());
  const [sector, setSector] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [desc, setDesc] = useState(true);
  const sectorId = useId();
  const minId = useId();

  const sectors = useMemo(
    () => [...new Set((data?.results ?? []).map((r) => r.sector).filter((s): s is string => !!s))].sort(),
    [data],
  );

  const rows = useMemo(() => {
    const list = (data?.results ?? []).filter(
      (r) =>
        (regimes.size === 0 || regimes.has(r.regime)) &&
        (!sector || r.sector === sector) &&
        r.composite >= minScore,
    );
    return [...list].sort((a, b) => (desc ? b.composite - a.composite : a.composite - b.composite));
  }, [data, regimes, sector, minScore, desc]);

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
          Screener // {INDEX} · {LIMIT} stocks · ranked by health score
        </h2>
        <div className="toolbar">
          <div className="field" role="group" aria-label="Filter by regime">
            <span>REGIME</span>
            {REGIMES.map((r) => (
              <button
                key={r}
                type="button"
                className="chip"
                aria-pressed={regimes.has(r)}
                style={{ ['--chip-color' as string]: colorHex(REGIME_COLOR_KEY[r]) }}
                onClick={() => toggleRegime(r)}
              >
                {r}
              </button>
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

          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setDesc((d) => !d)}
            aria-label={`Sort by score, currently ${desc ? 'descending' : 'ascending'}`}
          >
            SCORE {desc ? '▼' : '▲'}
          </button>

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
            {rows.length} of {data.count} stocks shown
          </p>
          <div className="list-header" aria-hidden="true">
            <span>#</span>
            <span>TICKER</span>
            <span>COMPANY</span>
            <span>REGIME</span>
            <span>HEALTH</span>
            <span>VAL · MOM · DEBT · QUAL · PROF</span>
          </div>
          {rows.length === 0 ? (
            <p className="empty">&gt; NO MATCHES. Loosen the filters.</p>
          ) : (
            <ol className="ticker-list">
              {rows.map((r, i) => (
                <li key={r.symbol}>
                  <TickerRow rank={i + 1} score={r} onOpen={onOpen} />
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
