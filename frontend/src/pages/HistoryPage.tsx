import { useState } from 'react';
import { api, errorMessage } from '../api/client';
import type { HistoryEntry, HistoryKind, HistoryResponse } from '../api/types';
import { RegimeBadge } from '../components/RegimeBadge';
import { ErrorAlert, Scanning } from '../components/Status';
import { useAsync } from '../hooks/useAsync';
import { formatIdr, formatPct01, formatSignedPct } from '../theme/format';
import { REGIME_COLOR_KEY } from '../theme/tokens';

const PAGE = 25;
const FILTERS: { id: HistoryKind | 'all'; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'company', label: 'Lookups' },
  { id: 'simulation', label: 'Simulations' },
];

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' });

interface Props {
  onOpen: (symbol: string) => void;
  refreshKey: number;
}

export function HistoryPage({ onOpen, refreshKey }: Props) {
  const [filter, setFilter] = useState<HistoryKind | 'all'>('all');
  const [offset, setOffset] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);

  const kind = filter === 'all' ? undefined : filter;
  const hist = useAsync<HistoryResponse>(`${filter}:${offset}:${refreshKey}:${nonce}`, (signal) =>
    api.history({ kind, limit: PAGE, offset }, signal),
  );

  const remove = async (id?: number) => {
    if (id == null && !window.confirm('Delete your entire history?')) return;
    setActionError(null);
    try {
      await api.deleteHistory(id);
      if (id == null) setOffset(0);
      setNonce((n) => n + 1);
    } catch (e) {
      setActionError(errorMessage(e));
    }
  };

  const data = hist.data;
  const total = data?.total ?? 0;

  return (
    <div className="stack">
      <div className="toolbar">
        <div role="group" aria-label="Filter history" style={{ display: 'flex', gap: 6 }}>
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              className="chip"
              aria-pressed={filter === f.id}
              onClick={() => {
                setFilter(f.id);
                setOffset(0);
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn btn-ghost" onClick={() => remove()} disabled={!total}>
          Clear history
        </button>
      </div>

      {actionError && (
        <div className="alert" role="alert">
          <span>! ERR // {actionError}</span>
        </div>
      )}
      {hist.loading && <Scanning label="LOADING HISTORY..." />}
      {hist.error != null && !hist.loading && <ErrorAlert error={hist.error} onRetry={hist.reload} />}

      {data && !hist.loading && (
        <section className="panel" aria-label="History">
          <h2 className="panel-title">
            &gt; History · {total} {total === 1 ? 'entry' : 'entries'}
          </h2>
          {data.results.length === 0 ? (
            <p className="empty">&gt; NOTHING YET. Look up a company or run a simulation.</p>
          ) : (
            <ul className="history-list">
              {data.results.map((e) => (
                <HistoryRow key={e.id} entry={e} onOpen={onOpen} onDelete={() => remove(e.id)} />
              ))}
            </ul>
          )}

          {total > PAGE && (
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
              >
                Prev
              </button>
              <span className="mono dim">
                {offset + 1}–{Math.min(offset + PAGE, total)} of {total}
              </span>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={offset + PAGE >= total}
                onClick={() => setOffset(offset + PAGE)}
              >
                Next
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function HistoryRow({ entry, onOpen, onDelete }: { entry: HistoryEntry; onOpen: (s: string) => void; onDelete: () => void }) {
  const r = entry.result;
  const isSim = entry.kind === 'simulation';
  return (
    <li className="history-row">
      <time className="mono dim" dateTime={entry.created_at}>
        {dateFmt.format(new Date(entry.created_at))}
      </time>
      <span className="mono history-kind">{isSim ? 'SIM' : 'LOOKUP'}</span>
      <button type="button" className="link-btn" onClick={() => onOpen(entry.symbol)} title={r.company_name}>
        {entry.symbol}
      </button>
      {r.regime && <RegimeBadge regime={r.regime} color={REGIME_COLOR_KEY[r.regime] ?? 'grey'} />}
      <span className="mono history-detail">
        {r.composite != null && `Score ${r.composite.toFixed(1)}`}
        {isSim
          ? ` · ${entry.params.days ?? '?'}d · E[r] ${formatSignedPct(r.expected_return_pct ?? 0)} · P(up) ${formatPct01(
              r.prob_price_up ?? 0,
            )}`
          : r.last_close_price != null && ` · ${formatIdr(r.last_close_price)}`}
      </span>
      <button type="button" className="btn btn-ghost history-del" onClick={onDelete} aria-label={`Delete ${entry.symbol} entry`}>
        ✕
      </button>
    </li>
  );
}
