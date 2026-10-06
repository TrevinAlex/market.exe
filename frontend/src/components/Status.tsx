import { useEffect, useState } from 'react';
import { ApiError, errorMessage } from '../api/client';

export function Scanning({ label = 'SCANNING...' }: { label?: string }) {
  return (
    <p className="terminal-line" role="status" aria-live="polite">
      &gt; {label}
      <span className="cursor" aria-hidden="true" />
    </p>
  );
}

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
    <div className={`alert${retryAfter != null ? ' alert-warn' : ''}`} role="alert">
      <span className="alert-icon" aria-hidden="true">
        <svg viewBox="0 0 20 20" width="18" height="18">
          <circle cx="10" cy="10" r="9" fill="currentColor" opacity="0.18" />
          <rect x="9" y="5" width="2" height="7" rx="1" fill="currentColor" />
          <rect x="9" y="13.5" width="2" height="2" rx="1" fill="currentColor" />
        </svg>
      </span>
      <span className="alert-msg">{msg}</span>
      {onRetry && (
        <button type="button" className="btn alert-retry" onClick={onRetry} disabled={waiting}>
          Retry
        </button>
      )}
    </div>
  );
}
