import { SECTOR_STRESS_PCT, SectorHeatmap } from '../components/SectorHeatmap';
import { ErrorAlert, Scanning } from '../components/Status';
import { Tip } from '../components/Tip';
import { RegimeTipText } from '../components/explainers';
import { useHeatmap } from '../hooks/useHeatmap';
import { REGIMES, REGIME_COLOR_KEY, colorHex } from '../theme/tokens';

const INDEX = 'LQ45';

export function HeatmapPage() {
  const { data, error, loading, reload } = useHeatmap(INDEX);
  const sectors = data?.sectors ?? [];
  const stressed = sectors.filter((s) => s.stressed_pct >= SECTOR_STRESS_PCT).length;

  return (
    <div className="stack">
      {loading && <Scanning label={`MAPPING ${INDEX} SECTORS...`} />}
      {error != null && !loading && <ErrorAlert error={error} onRetry={reload} />}

      {data && !loading && (
        <>
          <section className="panel">
            <h2 className="headline">
              <b>{stressed}</b> of {sectors.length} sectors{' '}
              <Tip
                text={`A sector is under stress when at least ${SECTOR_STRESS_PCT}% of its stocks are in the Stress or Distribution regime, meaning their health score is below 50. It signals broad weakness across the sector, not just one company.`}
              >
                under stress
              </Tip>
            </h2>
            <p className="note">
              {INDEX} · a sector is "under stress" when ≥{SECTOR_STRESS_PCT}% of its stocks are in Stress or
              Distribution. Tile colour follows the sector's average health score (red → cyan). Sorted most stressed first.
            </p>
            <ul className="legend" style={{ marginTop: 8 }} aria-label="Regime colour legend">
              {REGIMES.map((r) => (
                <li key={r}>
                  <i style={{ background: colorHex(REGIME_COLOR_KEY[r]) }} aria-hidden="true" />
                  <Tip text={<RegimeTipText regime={r} />}>{r}</Tip>
                </li>
              ))}
            </ul>
          </section>
          {sectors.length === 0 ? <p className="empty">&gt; NO SECTOR DATA.</p> : <SectorHeatmap sectors={sectors} />}
        </>
      )}
    </div>
  );
}
