import type { AgentMix } from '../api/types';
import { AGENT_KEYS, AGENT_META } from '../theme/tokens';
import { formatPct01 } from '../theme/format';

/** Stacked bar + roster of the 5 agent archetypes (fractions from the backend). */
export function AgentMixBar({ mix, agents }: { mix: AgentMix; agents?: number }) {
  return (
    <div>
      <div className="agentbar" aria-hidden="true">
        {AGENT_KEYS.map((k) => (
          <span
            key={k}
            title={`${AGENT_META[k].label}: ${formatPct01(mix[k], 1)}`}
            style={{ width: `${mix[k] * 100}%`, background: AGENT_META[k].color }}
          />
        ))}
      </div>
      <ul className="roster" aria-label={`Agent mix${agents ? ` of ${agents} agents` : ''}`}>
        {AGENT_KEYS.map((k) => (
          <li key={k}>
            <span>
              <i style={{ background: AGENT_META[k].color }} aria-hidden="true" />
              {AGENT_META[k].label}
            </span>
            <span className="mono">{formatPct01(mix[k], 1)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
