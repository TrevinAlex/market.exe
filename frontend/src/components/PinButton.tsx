import { baseTicker } from '../api/client';
import { usePins } from '../hooks/usePins';

/** ☆ / ★ toggle for a ticker. Renders nothing when pins are unavailable
 *  (logged out, or Supabase not configured). */
export function PinButton({ symbol, size = 'sm' }: { symbol: string; size?: 'sm' | 'lg' }) {
  const { available, isPinned, toggle, symbols, maxPins } = usePins();
  if (!available) return null;

  const sym = baseTicker(symbol);
  const pinned = isPinned(sym);
  const full = !pinned && symbols.length >= maxPins;

  return (
    <button
      type="button"
      className={`pin-btn${size === 'lg' ? ' lg' : ''}`}
      aria-pressed={pinned}
      aria-label={pinned ? `Unpin ${sym}` : `Pin ${sym}`}
      title={full ? `Pin limit reached (${maxPins})` : pinned ? 'Unpin' : 'Pin to your watchlist'}
      disabled={full}
      onClick={(e) => {
        e.stopPropagation(); // don't open the row underneath
        void toggle(sym);
      }}
    >
      <svg className="pin-star" viewBox="0 0 24 24" aria-hidden="true">
        <path
          d="M12 3.6l2.47 5.01 5.53.8-4 3.9.94 5.5L12 16.2l-4.94 2.6.94-5.5-4-3.9 5.53-.8L12 3.6z"
          fill={pinned ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth={1.7}
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
