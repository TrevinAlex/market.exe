import type { Regime } from '../api/types';
import { colorHex } from '../theme/tokens';

interface Props {
  regime: Regime | string;
  color: string;
  size?: 'sm' | 'lg';
}

/** HUD-style regime label, e.g. "[ ACCUMULATION ]". Always text, never colour alone. */
export function RegimeBadge({ regime, color, size = 'sm' }: Props) {
  return (
    <span
      className={`regime-badge${size === 'lg' ? ' lg' : ''}`}
      style={{ ['--regime' as string]: colorHex(color) }}
      aria-label={`Regime: ${regime}`}
    >
      [ {regime.toUpperCase()} ]
    </span>
  );
}
