import { api } from '../api/client';
import type { PinsResponse } from '../api/types';
import { ErrorAlert, Scanning } from '../components/Status';
import { PinButton } from '../components/PinButton';
import { TickerRow } from '../components/TickerRow';
import { useAsync } from '../hooks/useAsync';
import { usePins } from '../hooks/usePins';

interface Props {
  onOpen: (symbol: string) => void;
  /** Bumped by the parent so scores refresh when the tab is shown. */
  refreshKey: number;
}

/** The user's pinned stocks (watchlist) with live health scores. */
export function PinnedPage({ onOpen, refreshKey }: Props) {
  const { symbols, maxPins, error: pinError, available } = usePins();
  // Refetch when the tab is opened or the set of pins changes. Scores are
  // cached server-side, so re-opening the tab doesn't re-spend credits.
  const key = available ? `${refreshKey}:${[...symbols].sort().join(',')}` : null;
  const res = useAsync<PinsResponse>(key, (signal) => api.pins(true, signal));

  if (!available) {
    return pinError ? <ErrorAlert error={new Error(pinError)} /> : <Scanning label="LOADING PINS..." />;
  }

  // Keep the order of the live pin list (so an unpin disappears instantly).
  const scored = new Map((res.data?.pins ?? []).map((p) => [p.symbol, p.score]));
  const visible = symbols.filter((s) => !res.data || scored.has(s));

  return (
    <div className="stack">
      <section className="panel" aria-label="Pinned stocks">
        <h2 className="panel-title">
          &gt; Pinned · {symbols.length}/{maxPins}
        </h2>
        <p className="note" style={{ margin: 0 }}>
          Click ☆ on any stock in the screener or company page to pin it here.
        </p>
      </section>

      {pinError && (
        <div className="alert" role="alert">
          <span>! ERR // {pinError}</span>
        </div>
      )}
      {res.loading && !res.data && <Scanning label="SCORING PINNED STOCKS..." />}
      {res.error != null && !res.loading && <ErrorAlert error={res.error} onRetry={res.reload} />}

      {symbols.length === 0 ? (
        <p className="empty">&gt; NO PINNED STOCKS YET.</p>
      ) : (
        res.data && (
          <ol className="ticker-list" aria-busy={res.loading}>
            {visible.map((sym, i) => {
              const score = scored.get(sym);
              return (
                <li key={sym}>
                  {score ? (
                    <TickerRow rank={i + 1} score={score} onOpen={onOpen} />
                  ) : (
                    <div className="ticker-row pin-missing">
                      <span className="rank">#{i + 1}</span>
                      <span className="sym-cell">
                        <button type="button" className="sym link-btn" onClick={() => onOpen(sym)}>
                          {sym}
                        </button>
                        <PinButton symbol={sym} />
                      </span>
                      <span className="dim">Score unavailable right now.</span>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        )
      )}
    </div>
  );
}
