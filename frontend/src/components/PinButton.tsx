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
      <span aria-hidden="true">{pinned ? '★' : '☆'}</span>
    </button>
  );
}
