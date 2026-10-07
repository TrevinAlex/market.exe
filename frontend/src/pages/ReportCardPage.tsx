import { useId, useMemo, useState } from 'react';
import {
  BACKTEST,
  GLOSSARY,
  REPORT_CARD,
  REPORT_CAVEATS,
  filterGlossary,
  type Grade,
} from '../content/guide';

const GRADE_LABEL: Record<Grade, string> = { pass: 'PASS', warn: 'UNTESTED', fail: 'NO SKILL' };

export function ReportCardPage() {
  const [query, setQuery] = useState('');
  const searchId = useId();
  const groups = useMemo(() => filterGlossary(GLOSSARY, query), [query]);
  const passed = REPORT_CARD.filter((r) => r.grade === 'pass').length;

  return (
    <div className="stack">
      <section className="panel stack" aria-labelledby="rc-title">
        <div>
          <h2 className="headline rc-headline" id="rc-title">
            Model report card · <span className="rc-score">{passed}</span> of {REPORT_CARD.length} checks passed
          </h2>
          <p className="note">
            How the simulation holds up against real prices. Walk-forward test on {BACKTEST.stocks} LQ45 stocks,{' '}
            {BACKTEST.forecasts.toLocaleString('en-US')} forecasts of {BACKTEST.horizonDays} trading days,{' '}
            {BACKTEST.years}, {BACKTEST.source}. Each year was predicted using only earlier data.
          </p>
        </div>

        <div className="rc-table-wrap">
          <table className="rc-table">
            <caption className="sr-only">Backtest results for each model check</caption>
            <thead>
              <tr>
                <th scope="col">Check</th>
                <th scope="col">Result</th>
                <th scope="col">Target</th>
                <th scope="col">Grade</th>
                <th scope="col">What it means</th>
              </tr>
            </thead>
            <tbody>
              {REPORT_CARD.map((r) => (
                <tr key={r.metric}>
                  <th scope="row">{r.metric}</th>
                  <td className="mono rc-num">{r.result}</td>
                  <td className="mono dim rc-num">{r.target}</td>
                  <td>
                    <span className={`rc-grade rc-${r.grade}`}>{r.label ?? GRADE_LABEL[r.grade]}</span>
                  </td>
                  <td className="rc-meaning">{r.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rc-bottomline">
          <h3 className="panel-title">Bottom line</h3>
          <p>
            Use the simulation as a <b>risk range</b>: how far the price could realistically move in the next 30
            trading days. Don't use it to predict whether the price goes up or down.
          </p>
        </div>

        <ul className="rc-caveats note">
          {REPORT_CAVEATS.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      </section>

      <section className="panel stack" aria-labelledby="gl-title">
        <div className="rc-glossary-head">
          <h2 className="headline rc-headline" id="gl-title">
            Glossary
          </h2>
          <label htmlFor={searchId} className="field">
            SEARCH &gt;
          </label>
          <input
            id={searchId}
            className="input"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. probability"
            autoComplete="off"
            style={{ width: 200 }}
          />
        </div>

        {groups.length === 0 && <p className="empty">&gt; NO TERMS MATCH "{query}".</p>}

        {groups.map((g) => (
          <div key={g.title} className="stack">
            <h3 className="panel-title rc-group">{g.title}</h3>
            <dl className="rc-terms">
              {g.entries.map((e) => (
                <div key={e.term} className="rc-term">
                  <dt>
                    {e.term}
                    {e.aka && <span className="dim"> · {e.aka}</span>}
                  </dt>
                  <dd>
                    <p>{e.meaning}</p>
                    {e.good && (
                      <p className="rc-good">
                        <span className="rc-tag">GOOD</span> {e.good}
                      </p>
                    )}
                    {e.bad && (
                      <p className="rc-bad">
                        <span className="rc-tag">BAD</span> {e.bad}
                      </p>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </section>
    </div>
  );
}
