import type { FundamentalsYear } from '../api/types';
import { palette } from '../theme/tokens';
import { Tip } from './Tip';

/** Same bands as the health-score regimes (70 / 50 / 30). */
export function scoreColor(score: number | null): string {
  if (score == null) return palette.grey;
  if (score >= 70) return palette.cyan;
  if (score >= 50) return palette.yellow;
  if (score >= 30) return palette.amber;
  return palette.red;
}

const TREND_TEXT: Record<string, { label: string; color: string }> = {
  improving: { label: 'IMPROVING', color: palette.cyan },
  stable: { label: 'STABLE', color: palette.text },
  deteriorating: { label: 'DETERIORATING', color: palette.red },
};

const pct = (v: number | null) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);
const num = (v: number | null, d = 2) => (v == null ? '—' : v.toFixed(d));

interface Props {
  years: FundamentalsYear[];
  trend?: string | null;
}

/**
 * Yearly fundamentals from the Sectors Company Report, scored with today's
 * rules. Descriptive only: it shows whether the company's numbers have been
 * getting stronger or weaker, not where the price is going.
 */
export function FundamentalsHistory({ years, trend }: Props) {
  if (years.length === 0) return null;
  const t = trend ? TREND_TEXT[trend] : undefined;

  return (
    <section className="fund-history" aria-label="Fundamentals history">
      <h3 className="panel-title">
        <Tip text="Each fiscal year's ROE, ROA, debt/equity and P/E from Sectors, scored with the same rules as today's health score. Momentum is left out because it needs that year's price range, so the score covers 4 of the 5 parts, rescaled to 0-100. It describes the company's track record; it is not a price forecast.">
          Fundamentals history // {years[0].year}–{years[years.length - 1].year}
        </Tip>
        {t && (
          <span className="fund-trend" style={{ color: t.color }}>
            {' '}· {t.label}
          </span>
        )}
      </h3>

      <div className="fund-bars" role="img" aria-label={years.map((y) => `${y.year}: ${y.score ?? 'no data'}`).join(', ')}>
        {years.map((y) => (
          <div key={y.year} className="fund-bar">
            <span className="fund-bar-val mono">{y.score == null ? '—' : Math.round(y.score)}</span>
            <div className="fund-bar-track">
              <div
                className="fund-bar-fill"
                style={{ height: `${y.score ?? 0}%`, background: scoreColor(y.score) }}
              />
            </div>
            <span className="fund-bar-year mono">{y.year}</span>
          </div>
        ))}
      </div>

      <table className="subscore-table fund-table">
        <thead>
          <tr>
            <th scope="col">Year</th>
            <th scope="col">ROE</th>
            <th scope="col">ROA</th>
            <th scope="col">Debt/Eq</th>
            <th scope="col">P/E</th>
          </tr>
        </thead>
        <tbody>
          {years
            .slice()
            .reverse()
            .map((y) => (
              <tr key={y.year}>
                <th scope="row">{y.year}</th>
                <td>{pct(y.roe)}</td>
                <td>{pct(y.roa)}</td>
                <td>{num(y.der)}</td>
                <td>{num(y.pe, 1)}</td>
              </tr>
            ))}
        </tbody>
      </table>
      <p className="dim" style={{ margin: 0, fontSize: 11 }}>
        Source: Sectors Company Report (annual figures). A track record, not a forecast — see REPORT CARD.
      </p>
    </section>
  );
}
