import { useEffect, useId, useState, type FormEvent } from 'react';
import { baseTicker, normalizeTicker } from '../api/client';
import type { Regime, Score, SimulationResponse } from '../api/types';
import { AgentMixBar } from '../components/AgentMixBar';
import { FanChart } from '../components/FanChart';
import { FundamentalsHistory } from '../components/FundamentalsHistory';
import { HealthBar } from '../components/HealthBar';
import { PinButton } from '../components/PinButton';
import { RadarChart } from '../components/RadarChart';
import { RegimeBadge } from '../components/RegimeBadge';
import { ErrorAlert, Scanning } from '../components/Status';
import { Tip } from '../components/Tip';
import { HEALTH_EXPLAINER } from '../components/explainers';
import { isNoData, normalizedOf } from '../components/subScoreUtils';
import { useCompany } from '../hooks/useCompany';
import { useSimulate } from '../hooks/useSimulate';
import { formatIdr, formatPct01, formatSignedPct } from '../theme/format';
import { LOT_SIZE, formatIdrCompact, parseRupiah, positionRisk } from '../components/positionRisk';
import {
  REGIME_MEANING,
  SUB_SCORE_KEYS,
  SUB_SCORE_META,
  isFinancialSector,
  palette,
} from '../theme/tokens';

interface Props {
  symbol: string | null;
  onSymbol: (symbol: string) => void;
}

export function CompanyPage({ symbol, onSymbol }: Props) {
  const company = useCompany(symbol);
  const sim = useSimulate(symbol);

  return (
    <div className="stack">
      <TickerSearch current={symbol} onSubmit={onSymbol} />

      {!symbol && <p className="empty">&gt; ENTER A 4-LETTER IDX TICKER OR PICK ONE FROM THE SCREENER.</p>}
      {company.loading && <Scanning label={`SCANNING ${symbol}...`} />}
      {company.error != null && !company.loading && <ErrorAlert error={company.error} onRetry={company.reload} />}

      {company.data && !company.loading && (
        <>
          <CompanyOverview score={company.data} />
          <section className="panel stack" aria-label="Scenario simulation">
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-primary" onClick={sim.run} disabled={sim.loading}>
                [ {sim.data ? 'RE-RUN' : 'RUN'} SIMULATION ]
              </button>
              <p className="note">
                Range width comes from this stock's own volatility; known dividends are included. Agents add trading
                randomness, not direction.
              </p>
            </div>
            {sim.loading && <Scanning label="SIMULATING 500 RUNS × 1000 AGENTS..." />}
            {sim.error != null && !sim.loading && <ErrorAlert error={sim.error} onRetry={sim.run} />}
            {sim.data && !sim.loading && <SimulationPanel sim={sim.data} />}
          </section>
        </>
      )}
    </div>
  );
}

function TickerSearch({ current, onSubmit }: { current: string | null; onSubmit: (s: string) => void }) {
  const [value, setValue] = useState(current ?? '');
  const [invalid, setInvalid] = useState(false);
  const inputId = useId();
  const errId = useId();

  useEffect(() => {
    setValue(current ?? '');
    setInvalid(false);
  }, [current]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = normalizeTicker(value);
    if (!t) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onSubmit(t);
  };

  return (
    <form className="panel toolbar" onSubmit={submit} role="search" noValidate>
      <label htmlFor={inputId} className="field">
        TICKER &gt;
      </label>
      <input
        id={inputId}
        className="input"
        value={value}
        onChange={(e) => setValue(e.target.value.toUpperCase())}
        maxLength={4}
        placeholder="BBCA"
        autoComplete="off"
        spellCheck={false}
        pattern="[A-Za-z]{4}"
        aria-invalid={invalid}
        aria-describedby={invalid ? errId : undefined}
        style={{ width: 90, textTransform: 'uppercase', letterSpacing: '0.1em' }}
      />
      <button type="submit" className="btn">
        Scan
      </button>
      {invalid && (
        <span id={errId} role="alert" className="mono" style={{ color: 'var(--red)', fontSize: 12 }}>
          Ticker must be exactly 4 letters (e.g. BBCA)
        </span>
      )}
    </form>
  );
}

function CompanyOverview({ score }: { score: Score }) {
  const regime = score.regime as Regime;
  const bank = isFinancialSector(score.sector);

  return (
    <div className="company-grid">
      <section className="panel stack" aria-label="Health overview">
        <div className="company-head">
          <h2>{baseTicker(score.symbol)}</h2>
          <PinButton symbol={score.symbol} size="lg" />
          <span>{score.company_name}</span>
          <span className="dim" style={{ fontSize: 12 }}>
            {[score.sector, score.sub_sector].filter(Boolean).join(' / ') || '—'}
          </span>
        </div>
        <div className="company-head">
          <span className="price">{formatIdr(score.last_close_price)}</span>
          <span className="dim mono" style={{ fontSize: 11 }}>
            LAST CLOSE · DATA COVERAGE {formatPct01(score.confidence)}
          </span>
        </div>

        <div>
          <h3 className="panel-title" style={{ marginBottom: 6 }}>
            <Tip text={HEALTH_EXPLAINER}>Health score</Tip>
          </h3>
          <HealthBar
            score={score.composite}
            regime={score.regime}
            color={score.color}
            confidence={score.confidence}
            size="lg"
          />
        </div>

        <div>
          <RegimeBadge regime={score.regime} color={score.color} size="lg" explain />
          <p className="meaning">{REGIME_MEANING[regime] ?? ''}</p>
        </div>

        <table className="subscore-table">
          <caption className="sr-only">Sub-scores, each out of 20, with the input behind each one</caption>
          <thead>
            <tr>
              <th scope="col">Dimension</th>
              <th scope="col">
                <Tip text="The company's actual number behind each sub-score, and the rule that turns it into 0-20 points. Hover a dimension name to see what it measures.">
                  Why this score
                </Tip>
              </th>
              <th scope="col" style={{ width: '22%' }}>
                <span className="sr-only">Bar</span>
              </th>
              <th scope="col" className="num">
                Score
              </th>
            </tr>
          </thead>
          <tbody>
            {SUB_SCORE_KEYS.map((k) => {
              const v = score.sub_scores[k];
              const n = normalizedOf(k, score.sub_scores, score.sub_scores_normalized);
              const na = isNoData(k, v, score.confidence);
              const why = score.breakdown?.[k];
              return (
                <tr key={k}>
                  <th scope="row" style={{ color: na ? palette.grey : palette.text }}>
                    <Tip text={SUB_SCORE_META[k].measures}>{SUB_SCORE_META[k].label}</Tip>
                    {k === 'debt' && bank && (
                      <span
                        className="info-icon"
                        style={{ marginLeft: 6 }}
                        title="Leverage is structurally high for banks."
                        aria-label="Note: leverage is structurally high for banks."
                        role="img"
                      >
                        i
                      </span>
                    )}
                  </th>
                  <td>
                    {why ? (
                      <>
                        <div className="why-input" style={{ color: why.input ? palette.text : palette.grey }}>
                          {why.input ?? 'No data · scored neutral 10 / 20'}
                        </div>
                        <div className="why-rule">{why.rule}</div>
                      </>
                    ) : (
                      <span className="dim" style={{ fontFamily: 'var(--font-sans)' }}>
                        {SUB_SCORE_META[k].measures}
                      </span>
                    )}
                  </td>
                  <td>
                    <div className={`minibar${na ? ' na' : ''}`} aria-hidden="true">
                      <span style={{ width: `${na ? 50 : n * 100}%` }} />
                    </div>
                  </td>
                  <td className="num" title={na ? 'N/A: no data' : undefined}>
                    {na ? 'N/A' : `${v.toFixed(2)} / 20`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {bank && (
          <p className="note">
            <span className="info-icon" aria-hidden="true">
              i
            </span>{' '}
            Leverage is structurally high for banks, so the debt score sits near 0 by design.
          </p>
        )}
      </section>

      <section className="panel" aria-label="Sub-score radar" style={{ display: 'grid', placeItems: 'center' }}>
        <h3 className="panel-title" style={{ justifySelf: 'start' }}>
          Signal profile
        </h3>
        <RadarChart
          subScores={score.sub_scores}
          normalized={score.sub_scores_normalized}
          confidence={score.confidence}
          size={300}
        />
      </section>
    </div>
  );
}

function SimulationPanel({ sim }: { sim: SimulationResponse }) {
  const ret = sim.expected_return_pct;
  const retColor = ret > 0 ? palette.cyan : ret < 0 ? palette.red : palette.text;
  const up = sim.prob_price_up;
  const days = sim.horizon_days;

  return (
    <div className="stack">
      <dl className="stat-grid" style={{ margin: 0 }}>
        <Stat
          label="Expected return"
          value={formatSignedPct(ret)}
          color={retColor}
          tip={`The change from today's price to the median (P50) outcome of ${sim.runs} simulated runs after ${days} days. It sits near 0% by design: the model doesn't claim a direction. See REPORT CARD.`}
        />
        <Stat
          label="Probability up"
          value={formatPct01(up)}
          color={up >= 0.5 ? palette.cyan : palette.amber}
          tip={`The share of simulated runs that ended above today's price after ${days} days. Around 50% is expected: backtests showed 30-day direction is a coin flip, so the model doesn't claim one. Below 50% usually means a dividend is due. See REPORT CARD.`}
        />
        <Stat
          label="Bearish (p10)"
          value={formatIdr(sim.bands.p10)}
          color={palette.red}
          tip={`A plausible downside case. 10% of simulated runs ended at or below this price after ${days} days, and 90% ended above it.`}
        />
        <Stat
          label="Median (p50)"
          value={formatIdr(sim.bands.p50)}
          tip={`The middle outcome. Half of the simulated runs ended above this price after ${days} days and half ended below it.`}
        />
        <Stat
          label="Bullish (p90)"
          value={formatIdr(sim.bands.p90)}
          color={palette.cyan}
          tip={`A plausible upside case. Only 10% of simulated runs ended above this price after ${days} days.`}
        />
      </dl>

      <PositionRiskCalc sim={sim} />

      <FundamentalsHistory years={sim.fundamentals ?? []} trend={sim.fundamentals_trend} />

      <div>
        <h3 className="panel-title">
          Price fan // {sim.horizon_days}d horizon · {sim.runs} runs
        </h3>
        <FanChart
          paths={sim.sample_paths}
          bands={sim.bands}
          dailyBands={sim.daily_bands ?? undefined}
          events={sim.events ?? []}
          currentPrice={sim.current_price}
          horizonDays={sim.horizon_days}
        />
      </div>

      <div>
        <h3 className="panel-title">Agent mix // {sim.agents.toLocaleString('en-US')} agents</h3>
        <AgentMixBar mix={sim.agent_mix} agents={sim.agents} />
      </div>
    </div>
  );
}

function PositionRiskCalc({ sim }: { sim: SimulationResponse }) {
  const inputId = useId();
  const hintId = useId();
  const [text, setText] = useState('10.000.000');
  const amount = parseRupiah(text);
  const risk = amount == null ? null : positionRisk(amount, sim.current_price, sim.bands);
  const days = sim.horizon_days;
  const worst = risk?.outcomes[0];

  const labels: Record<string, { name: string; color: string; tip: string }> = {
    p10: {
      name: 'Bad case (P10)',
      color: palette.red,
      tip: `1 in 10 simulated runs ended worse than this after ${days} trading days.`,
    },
    p50: {
      name: 'Middle case (P50)',
      color: palette.text,
      tip: 'Half of the runs ended above this and half below. Not a prediction of direction.',
    },
    p90: {
      name: 'Good case (P90)',
      color: palette.cyan,
      tip: `Only 1 in 10 simulated runs ended better than this after ${days} trading days.`,
    },
  };

  return (
    <section className="risk-calc" aria-label="Position risk calculator">
      <h3 className="panel-title">Position risk // what could {amount ? formatIdrCompact(amount) : 'your money'} become?</h3>
      <div className="toolbar">
        <label htmlFor={inputId} className="field">
          IF I INVEST Rp &gt;
        </label>
        <input
          id={inputId}
          className="input"
          inputMode="numeric"
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-invalid={amount == null}
          aria-describedby={hintId}
          style={{ width: 160 }}
        />
        <span id={hintId} className="dim mono" style={{ fontSize: 11 }}>
          {amount == null
            ? 'Enter an amount, e.g. 10.000.000 or 10jt'
            : risk && risk.lots > 0
              ? `≈ ${risk.lots.toLocaleString('en-US')} lot${risk.lots === 1 ? '' : 's'} at ${formatIdr(sim.current_price)}`
              : `Less than 1 lot (${formatIdr(sim.current_price * LOT_SIZE)})`}
        </span>
      </div>

      {risk && worst && (
        <>
          <dl className="stat-grid" style={{ margin: 0 }}>
            {risk.outcomes.map((o) => (
              <div key={o.key} className="stat" style={{ ['--stat' as string]: labels[o.key].color }}>
                <dt>
                  <Tip text={labels[o.key].tip}>{labels[o.key].name}</Tip>
                </dt>
                <dd>{formatIdrCompact(o.value)}</dd>
                <dd className="risk-change">
                  {formatIdrCompact(o.change, true)} ({formatSignedPct(o.changePct)})
                </dd>
              </div>
            ))}
          </dl>
          <p className="risk-summary">
            {worst.change < 0 ? (
              <>
                Realistic worst case: <strong style={{ color: palette.red }}>{formatIdrCompact(worst.change)}</strong>{' '}
                in {days} trading days, with a 1 in 10 chance it's worse.
              </>
            ) : (
              <>Even the bad case ends above today's price; dividends or a calm stock can do that.</>
            )}{' '}
            <span className="dim">
              Backtested: real outcomes fell below the bad case about 1 in 10 times. Excludes fees and taxes.
            </span>
          </p>
        </>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  color,
  tip,
}: {
  label: string;
  value: string;
  color?: string;
  tip?: string;
}) {
  return (
    <div className="stat" style={color ? { ['--stat' as string]: color } : undefined}>
      <dt>{tip ? <Tip text={tip}>{label}</Tip> : label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
