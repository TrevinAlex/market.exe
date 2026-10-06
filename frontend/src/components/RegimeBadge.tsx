import type { Regime } from '../api/types';
import { REGIMES, colorHex } from '../theme/tokens';
import { RegimeTipText } from './explainers';
import { Tip } from './Tip';

interface Props {
  regime: Regime | string;
  color: string;
  size?: 'sm' | 'lg';
  /** Show a hover/focus pop-up explaining what this regime means. */
  explain?: boolean;
}

const isRegime = (r: string): r is Regime => (REGIMES as string[]).includes(r);

/** Regime label pill, e.g. "Accumulation". Always text, never colour alone. */
export function RegimeBadge({ regime, color, size = 'sm', explain = false }: Props) {
  const badge = (
    <span
      className={`regime-badge${size === 'lg' ? ' lg' : ''}`}
      style={{ ['--regime' as string]: colorHex(color) }}
      aria-label={`Regime: ${regime}`}
    >
      {regime}
    </span>
  );

  if (!explain || !isRegime(regime)) return badge;
  return <Tip text={<RegimeTipText regime={regime} />}>{badge}</Tip>;
}
