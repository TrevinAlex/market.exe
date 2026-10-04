import { useEffect, useState } from 'react';
import { ApiError, errorMessage } from '../api/client';

/** Terminal-style loading line: "> SCANNING..█" */
export function Scanning({ label = 'SCANNING...' }: { label?: string }) {
  return (
    <p className="terminal-line" role="status" aria-live="polite">
      &gt; {label}
      <span className="cursor" aria-hidden="true" />
    </p>
  );
}

/** Red HUD alert. For 429s it counts down the Retry-After window before enabling retry. */
export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const retryAfter = error instanceof ApiError && error.status === 429 ? error.retryAfter : null;
  const [left, setLeft] = useState<number | null>(retryAfter);

  useEffect(() => {
    setLeft(retryAfter);
    if (retryAfter == null || retryAfter <= 0) return;
    const id = window.setInterval(() => {
      setLeft((s) => {
        if (s == null || s <= 1) {
          window.clearInterval(id);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(id);
  }, [error, retryAfter]);

  const msg = left != null ? `Rate limited, retry in ${left}s` : errorMessage(error);
  const waiting = left != null && left > 0;

  return (
    <div className="alert" role="alert">
      <span>! ERR // {msg}</span>
      {onRetry && (
        <button type="button" className="btn" onClick={onRetry} disabled={waiting}>
          Retry
        </button>
      )}
    </div>
  );
}
