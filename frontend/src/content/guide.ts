import type { Regime } from '../api/types';
import { REGIMES, REGIME_MEANING, REGIME_RANGE, SUB_SCORE_META } from '../theme/tokens';

export type Grade = 'pass' | 'warn' | 'fail';

export interface ReportRow {
  metric: string;
  result: string;
  target: string;
  grade: Grade;
  label?: string;
  meaning: string;
}

export const BACKTEST = {
  stocks: 45,
  forecasts: 15426,
  years: '2019–2026',
  horizonDays: 30,
  source: 'daily closing prices',
} as const;

export const REPORT_CARD: ReportRow[] = [
  {
    metric: 'Real price lands inside the P10–P90 range',
    result: '79.5%',
    target: '80%',
    grade: 'pass',
    meaning:
      'The main promise of the simulation. The range is meant to catch 8 out of 10 real outcomes, and it does. ' +
      'An earlier version with one fixed volatility for every stock only caught 39%.',
  },
  {
    metric: 'Real price lands inside the P25–P75 range',
    result: '52.0%',
    target: '50%',
    grade: 'pass',
    meaning: 'The tighter middle range is also honest: about half of real outcomes fall inside it.',
  },
  {
    metric: 'Range width adapts to each stock',
    result: '0.63 correlation',
    target: 'higher is better',
    grade: 'pass',
    meaning:
      "Each stock's volatility is predicted from its last ~60 trading days and its 52-week range, so a calm bank " +
      'gets a narrow range and a volatile miner a wide one. Correlation with the volatility that actually followed: ' +
      '0.63, up from 0.55 using the 52-week range alone. Adding 1-year volatility or the sector was tested and ' +
      'rejected: neither improved accuracy.',
  },
  {
    metric: 'Known dividends',
    result: '+2.4% → −1.3% bias',
    target: 'close to 0%',
    grade: 'pass',
    meaning:
      'When an ex-dividend date falls inside the 30 days, the price drops by about the dividend. Modelling that cut ' +
      'the median forecast error in those windows from 2.4% too high to 1.3% too low.',
  },
  {
    metric: 'Holds up in a market crash',
    result: '65% in 2020',
    target: '80%',
    grade: 'warn',
    label: 'WEAK SPOT',
    meaning:
      'Every other year landed between 79% and 85%, but in the 2020 COVID crash only 65% of outcomes fell inside ' +
      'the range: volatility jumped faster than any recent-history model can see. Expect ranges to be too narrow ' +
      'in the first weeks of a crash, and too wide for very calm large caps such as BBCA.',
  },
  {
    metric: 'Predicting up vs down',
    result: '≈ 50%',
    target: 'above 50%',
    grade: 'fail',
    meaning:
      'Nothing we tested beat a coin flip at calling the direction over 30 days: not the agent mix, not a logistic ' +
      'regression, not boosted trees. The 52% in the latest run is no better than always guessing "down" (53%). ' +
      "So the app doesn't claim to know direction. Probability up stays near 50% on purpose.",
  },
  {
    metric: 'Agents that react to the price',
    result: 'no gain',
    target: 'better than ignoring the price',
    grade: 'fail',
    label: 'REJECTED',
    meaning:
      'We let agents react to the last 5 days: herding (falls recruit panic sellers) and contrarian (falls recruit ' +
      'value buyers). Strengths were picked on 2019–2022 and judged on 2023–2026. Herding made the ranges worse; ' +
      'contrarian was within random noise and pulled the 80% range below target. So the normal forecast keeps ' +
      'agents that ignore the price.',
  },
  {
    metric: 'Stress scenarios match real 2020 episodes',
    result: '32 / 40 panic · 26 / 40 rally',
    target: '80% inside P10–P90',
    grade: 'warn',
    label: 'WHAT-IF',
    meaning:
      'The 2020-style panic and rally scenarios are fitted to the worst (11 Feb–24 Mar 2020, median stock −44%) and ' +
      'best (4 Nov–17 Dec 2020, +32%) 30-day stretches for LQ45. Real outcomes landed inside the scenario range for ' +
      '80% and 65% of stocks; the normal forecast caught 1 and 11 of 40. Each is fitted to one episode, so it ' +
      'describes that episode rather than predicting the next one.',
  },
  {
    metric: 'Health score as a return predictor',
    result: 'not tested',
    target: '—',
    grade: 'warn',
    meaning:
      "Testing whether healthy stocks go on to outperform needs each year's fundamentals as they were known at the " +
      'time, for every stock. Sectors has this history (the Fundamentals history panel shows it), but a fair test ' +
      'across 45 stocks would cost about 90 API credits, so it is on the roadmap. Read the health score as a ' +
      'description of the company today, not a forecast.',
  },
];

export const REPORT_CAVEATS = [
  "The test used stocks that are in LQ45 today, which slightly favours companies that did well (survivorship bias).",
  'Past accuracy is no guarantee of future accuracy. Market crashes can produce moves wider than any range.',
  'Forecasts are for the raw share price. Dividends you would receive are not added back.',
  'Accuracy varies by stock: calm large caps (banks, consumer staples) land inside the range more often than 80%, ' +
    'and stocks that trended hard (e.g. ARTO, BRPT in 2020–21) less often.',
];

export interface GlossaryEntry {
  term: string;
  aka?: string;
  meaning: string;
  good?: string;
  bad?: string;
}

export interface GlossaryGroup {
  title: string;
  entries: GlossaryEntry[];
}

const regimeEntry = (r: Regime): GlossaryEntry => ({
  term: r,
  aka: `health ${REGIME_RANGE[r]}`,
  meaning: REGIME_MEANING[r],
});

const meta = SUB_SCORE_META;

export const GLOSSARY: GlossaryGroup[] = [
  {
    title: 'Health & regimes',
    entries: [
      {
        term: 'Health score',
        aka: '0–100, the HP bar',
        meaning:
          "A summary of the company's financial condition, shown like a game HP bar. It is the sum of five sub-scores " +
          'worth up to 20 points each. It describes the company today; it is not a price forecast.',
        good: '70 or more: strong on most of the five dimensions.',
        bad: 'Below 30: several red flags at once. The bar pulses red.',
      },
      {
        term: 'Regime',
        meaning:
          'The phase the stock appears to be in, decided only by its health score. The marks on the HP bar at 30, 50 ' +
          'and 70 are the boundaries between regimes.',
      },
      ...REGIMES.map(regimeEntry),
      {
        term: 'Data coverage',
        aka: 'confidence',
        meaning:
          'How many of the five sub-scores were calculated from real data. A missing input gets a neutral 10/20 instead.',
        good: '100%: every sub-score is backed by data.',
        bad: 'Below 60%: marked LOW SIGNAL and the HP bar fades. Treat the score with caution.',
      },
      {
        term: 'Fundamentals history',
        aka: 'yearly track record',
        meaning:
          "Each past fiscal year's ROE, ROA, debt/equity and P/E from the Sectors Company Report, scored with the same " +
          "rules as today's health score. Momentum is left out (it needs that year's price range), so it covers 4 of the 5 " +
          'parts, rescaled to 0–100. The trend compares the latest year with the average of the three before it.',
        good: 'IMPROVING: the latest year scores at least 5 points above its recent average.',
        bad: "DETERIORATING: at least 5 points below. A track record, not a forecast — it doesn't say where the price goes.",
      },
      {
        term: 'Sector under stress',
        meaning:
          'A sector where at least half of the stocks are in Stress or Distribution (health below 50). It signals ' +
          'weakness across the whole sector, not just one company.',
      },
    ],
  },
  {
    title: 'The five sub-scores (0–20 each)',
    entries: [
      {
        term: meta.valuation.label,
        aka: 'VAL · P/E',
        meaning: `${meta.valuation.measures}. How expensive the share is compared with the profit behind it.`,
        good: 'P/E around 5–15: you pay little for each rupiah of profit.',
        bad: 'P/E above 25, or no profit at all (negative P/E scores as missing).',
      },
      {
        term: meta.momentum.label,
        aka: 'MOM',
        meaning: `${meta.momentum.measures}. Where the price sits between its lowest and highest point of the last year.`,
        good: 'About two thirds of the way up the 52-week range, with a positive day.',
        bad:
          'Near the 52-week low (falling), or at the very top (may be overheated). In the backtest, momentum alone ' +
          'did not predict the next 30 days.',
      },
      {
        term: meta.debt.label,
        aka: 'DEBT · D/E',
        meaning: `${meta.debt.measures}. How much the company borrows compared with what shareholders own.`,
        good: 'Debt-to-equity below about 0.5.',
        bad:
          '2.5 or more scores zero. Banks are the exception: borrowing is their business, so their debt score is ' +
          'naturally low (the app shows an info icon).',
      },
      {
        term: meta.quality.label,
        aka: 'QUAL · ROE',
        meaning: `${meta.quality.measures}. Profit earned for every rupiah shareholders put in.`,
        good: 'ROE of 15% or more (25% earns full marks).',
        bad: 'ROE below about 5%, or negative (a loss).',
      },
      {
        term: meta.profitability.label,
        aka: 'PROF · ROA',
        meaning: `${meta.profitability.measures}. Profit earned on everything the company owns.`,
        good: 'ROA of 10% or more (15% earns full marks).',
        bad: 'ROA below about 2%. Banks usually run 1–3%, which is normal for them.',
      },
    ],
  },
  {
    title: 'Simulation',
    entries: [
      {
        term: 'Probability up',
        meaning:
          "The share of the simulated runs that ended above today's price after 30 trading days.",
        good:
          'Reading it right: about 50% means the model claims no direction, which is honest. The backtest showed ' +
          'direction over 30 days is a coin flip. A value below 50% usually means a dividend falls inside the 30 days.',
        bad: 'Reading it wrong: treating 55% as a buy signal. A few points away from 50% is noise, not an edge.',
      },
      {
        term: 'Expected return',
        meaning:
          "The change from today's price to the median (P50) outcome. By design it sits close to 0%.",
        good: 'Near 0%: no direction claimed.',
        bad:
          'A negative value when a dividend is due is not a loss: the price drops because shareholders receive the ' +
          'dividend in cash.',
      },
      {
        term: 'Bearish (P10)',
        aka: '10th percentile',
        meaning:
          'A realistic bad case. 10% of simulated runs ended at or below this price; 90% ended above it.',
        good: 'Close to today: limited downside over the next 30 days.',
        bad: 'Far below today: ask yourself whether you could hold through a drop that size.',
      },
      {
        term: 'Median (P50)',
        aka: '50th percentile',
        meaning: 'The middle outcome. Half of the runs ended above it and half below.',
      },
      {
        term: 'Bullish (P90)',
        aka: '90th percentile',
        meaning: 'A realistic good case. Only 10% of runs ended above this price.',
      },
      {
        term: 'P10–P90 range',
        aka: '80% range',
        meaning:
          'Where the price should land 8 times out of 10. Its width measures risk: the wider the range, the bigger ' +
          'the swings to expect.',
        good: 'Narrow (under ~20% of the price): a calm stock.',
        bad: 'Wide (over ~40%): a volatile stock that can move a lot in a month, either way.',
      },
      {
        term: 'Price fan',
        aka: 'sample paths',
        meaning:
          'A handful of the simulated price paths, drawn as thin lines. The extreme lines are rare cases on purpose: ' +
          'about 1 path in 10 ends beyond each of P10 and P90.',
      },
      {
        term: 'Horizon',
        meaning: 'How far ahead the simulation looks: 30 trading days, about six calendar weeks.',
      },
      {
        term: 'Runs',
        meaning:
          'How many separate futures are simulated (500 by default). More runs give smoother percentiles but take longer.',
      },
      {
        term: 'Agents & agent mix',
        meaning:
          "1,000 simulated traders: panic sellers, momentum buyers, value buyers, profit takers and passive holders. " +
          "The mix is set from the stock's sub-scores and adds realistic day-to-day randomness. Their overall push up " +
          'or down is switched off, because the backtest showed it made forecasts worse. In the stress scenarios ' +
          'the crowd changes: panic sellers or momentum buyers flood in and move the price.',
      },
      {
        term: 'Stress scenario',
        aka: '2020-style panic / rally',
        meaning:
          'A what-if, not a forecast: what this stock could do if a 2020-sized crash or rally hit again. Each one is ' +
          'fitted to how LQ45 stocks really moved in that stretch. Switching scenarios costs no extra API credits.',
        good: 'Use it to ask "could I live with this loss?" before buying.',
        bad: 'Not a prediction that a crash or rally is coming.',
      },
      {
        term: 'Exit liquidity',
        meaning:
          "How easily you could sell your amount. Compares it with a typical day's trading (median of the last 20 " +
          'trading days) and estimates the price impact of selling it all in one day with the square-root rule from ' +
          'market-impact research: daily volatility × √(your amount ÷ a day\'s trading). A rough estimate that ' +
          'ignores bid-ask spread and auto-rejection limits.',
        good: "Under 1% of a day's trading: easy to sell.",
        bad: "Over 10%: selling quickly moves the price against you, or takes several days.",
      },
      {
        term: 'Daily volatility',
        meaning:
          'The typical size of one day\'s price move. Predicted from the last ~60 trading days and the 52-week range, ' +
          'and it sets how wide the range is.',
        good: 'About 1–1.5% a day: a calm large-cap such as a big bank.',
        bad: '3% a day or more: a volatile stock (e.g. coal, nickel or tech names).',
      },
      {
        term: 'Ex-dividend date',
        meaning:
          'The first day a buyer no longer gets the upcoming dividend. The price usually drops by about the dividend ' +
          'that day, and the simulation includes that drop.',
      },
    ],
  },
  {
    title: 'Market terms',
    entries: [
      {
        term: 'LQ45',
        meaning:
          'An Indonesia Stock Exchange (IDX) index of the 45 most liquid stocks, reviewed twice a year. The screener and heatmap use it.',
      },
      {
        term: '52-week range',
        meaning: 'The lowest and highest closing price over the last year.',
      },
      {
        term: 'P/E',
        aka: 'price-to-earnings',
        meaning: 'Share price divided by profit per share. Years of current profit you pay for when you buy.',
      },
      {
        term: 'D/E',
        aka: 'debt-to-equity',
        meaning: 'Total debt divided by shareholders\' equity.',
      },
      {
        term: 'ROE',
        aka: 'return on equity',
        meaning: "Yearly profit divided by shareholders' equity.",
      },
      {
        term: 'ROA',
        aka: 'return on assets',
        meaning: 'Yearly profit divided by total assets.',
      },
      {
        term: 'Rp / IDR',
        meaning: 'Indonesian rupiah. All prices are per share.',
      },
    ],
  },
];

export function filterGlossary(groups: GlossaryGroup[], query: string): GlossaryGroup[] {
  const q = query.trim().toLowerCase();
  if (!q) return groups;
  return groups
    .map((g) => ({
      ...g,
      entries: g.entries.filter((e) =>
        [e.term, e.aka, e.meaning, e.good, e.bad].some((s) => s?.toLowerCase().includes(q)),
      ),
    }))
    .filter((g) => g.entries.length > 0);
}
