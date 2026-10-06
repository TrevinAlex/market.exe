# MARKET.EXE

**Stock health and profitability simulator for the Indonesia Stock Exchange (IDX).**
Built for the Sectors Hackathon 2026, Track 3 · Market Intelligence.

MARKET.EXE turns raw [Sectors](https://sectors.app) data into signals the API doesn't provide:

- **Health score (0–100), shown as a game HP bar.** Five derived sub-scores combined into one number.
- **Market regime.** Each stock is labelled Accumulation, Recovery, Distribution or Stress.
- **Sector heatmap.** Which LQ45 sectors are under stress.
- **30-day scenario simulator.** A backtested range of where the price could realistically be in 30 trading days, with a position risk calculator in Rupiah.
- **Fundamentals history.** Each company's yearly ROE, ROA, debt/equity and P/E from the Sectors Company Report, scored with the same rules, so you can see whether its health is improving or deteriorating.
- **Model report card.** How accurate the simulator was against real prices, including where it's weak, plus a glossary of every term in the app.

> For informational purposes only. Not a recommendation to buy or sell securities.

## Quick start (Windows)

You need **Python 3** (developed and tested on 3.14), **Node.js 20+** and a Sectors API key.

```powershell
cd backend
copy .env.example .env
# edit .env: set SECTORS_API_KEY (and optionally the Supabase keys, see below)
cd ..
.\run.bat
```

`run.bat` does the following:
- creates or repairs `backend\.venv` and installs `requirements.txt`;
- runs `npm install` for the frontend on first use;
- checks that ports 8000 and 5173 are free;
- starts both servers in their own windows and opens [http://127.0.0.1:5173](http://127.0.0.1:5173).

Close the two windows (or press `Ctrl+C` in them) to stop the servers.

**Manual start:**

```powershell
# backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

The backend reads `.env` from the folder it is started in, so start it from inside `backend\`. It only reads `.env` at startup: restart it after editing the file.

## Project layout

```
market.exe/
├── run.bat                    # one-click start for backend + frontend
├── backend/                   # Python, FastAPI
│   ├── app/
│   │   ├── main.py            # routes
│   │   ├── core/scoring.py    # 5 sub-scores -> health score -> regime
│   │   ├── core/simulation.py # agent-based Monte Carlo + volatility model + dividends
│   │   ├── services/          # Sectors client (cached), Supabase history + pins
│   │   ├── auth.py, users.py  # user accounts (SQLite) and admin login
│   │   └── security.py        # rate limit, security headers, CORS
│   ├── supabase/schema.sql    # tables for history and pins
│   └── test_*.py              # offline tests (no API key or credits needed)
└── frontend/                  # React, Vite, TypeScript (see frontend/README.md)
    └── src/
        ├── pages/             # Screener, Heatmap, Company, Report card, Pinned, History
        ├── components/        # HP bar, regime badge, fan chart, heatmap, tooltips...
        └── content/guide.ts   # report card numbers and glossary text
```

## How it works

### Health score and regimes

`backend/app/core/scoring.py` scores each company on five dimensions, 0–20 points each:

| Sub-score | Input | Full marks |
|---|---|---|
| Valuation | Forward P/E on a 5–25 band | P/E 5 or lower |
| Momentum | Position in the 52-week range, plus the latest daily change | About 65% up the range |
| Debt | Debt-to-equity | D/E of 0 (2.5+ scores zero) |
| Quality | Return on equity | ROE 25% |
| Profitability | Return on assets | ROA 15% |

The five add up to the 0–100 health score, which maps to a regime:

| Regime | Score |
|---|---|
| Accumulation | 70–100 |
| Recovery | 50–69.9 |
| Distribution | 30–49.9 |
| Stress | 0–29.9 |

Missing data gets a neutral 10/20 and lowers the score's *confidence* (data coverage). Below 60% coverage, the app marks the score LOW SIGNAL.

### Scenario simulator

`backend/app/core/simulation.py` runs 500 Monte Carlo futures of 30 trading days each:

- **Volatility.** Each stock's daily volatility comes from a regression model. Its inputs are the last ~60 trading days of prices and the 52-week range. This sets how wide the range is.
- **Dividends.** Known dividends whose ex-date falls inside the horizon lower the price by the dividend amount on that day.
- **Agents.** 1,000 agents trade each day: panic sellers, momentum and value buyers, profit takers and passive holders. The mix comes from the sub-scores and adds realistic day-to-day randomness. Their overall up/down bias is switched off (`drift_scale = 0`), because the backtest showed it made forecasts worse.

The output is the P10 / P25 / P50 / P75 / P90 price range, sample paths for the fan chart, the agent mix and any dividend events.

### Backtest results (shown on the Report card tab)

**Setup:** a walk-forward test with 15,426 forecasts on 45 LQ45 stocks, 2019–2026, using daily prices. Each year was predicted with models trained only on earlier data.

| Check | Result | Target |
|---|---|---|
| Real price inside the P10–P90 range | **79.5%** | 80% |
| Real price inside the P25–P75 range | **52.0%** | 50% |
| Range width tracks real volatility (correlation) | **0.63** (52-week range alone: 0.55) | higher is better |
| Dividend windows, median forecast bias | +2.4% → **−1.3%** | ~0% |
| 2020 COVID crash, inside P10–P90 | 65% (other years 79–85%) | 80% |
| Predicting up vs down (agents, logistic regression, boosted trees) | ≈ 50% | > 50% |

For comparison, the first version of the simulator, with one fixed volatility for every stock, caught only 39% of outcomes in its "80%" range.

**What this means:** MARKET.EXE does what most stock tools only claim to do. Its price ranges are measured against real outcomes, and they hold up. When the app says there's an 80% chance the price lands between two values, that happened 79.5% of the time across 15,426 real cases. That makes it a reliable tool for the question investors most need answered before buying: *how much could this realistically move in the next six weeks?*

We tested direction too. Three different models, from simple to machine learning, couldn't call up versus down better than chance over 30 days, which is consistent with financial research on large, liquid stocks. So MARKET.EXE deliberately doesn't sell a direction call it can't back up. That's why "probability up" sits near 50%: it reflects a model that reports what the evidence supports.

**Where it's weaker, and what we tried:**
- **Crashes.** In the first weeks of a crash, volatility jumps faster than any model built on recent prices can see. That's why 2020 caught only 65%.
- **Stock by stock.** Accuracy varies by stock. Calm large caps land inside the range more often than 80% (BBCA 90%), while stocks that trended hard land inside it less often (ARTO 65%, BRPT 67% during the 2020–21 boom).
- **Rejected fixes.** We tested adding 1-year volatility, the sector, and a separate setting per stock to the volatility model. None improved overall accuracy, so none were shipped. The remaining misses come from sustained trends, which is a direction problem, not a volatility one.

The health score is a transparent snapshot of a company's financial condition today, built from five clearly defined measures, and the Fundamentals history panel shows how it has moved year by year. Testing whether it predicts future returns needs each year's fundamentals for every stock (about 90 Sectors credits for LQ45), and that's the next step on the roadmap.

**Caveat:** the test used stocks in LQ45 today, which slightly favours stocks that did well (survivorship bias).

To reproduce the backtest (free Yahoo Finance prices, no Sectors credits), run from the repo root:

```powershell
backend\.venv\Scripts\python.exe backtest\run_backtest.py --quick   # 8 stocks, about 2 minutes
backend\.venv\Scripts\python.exe backtest\run_backtest.py --dump backtest\data\forecasts.json   # all 45 stocks, about 10 minutes
backend\.venv\Scripts\python.exe backtest\calibration_breakdown.py   # accuracy by year, sector, volatility and stock
backend\.venv\Scripts\python.exe backtest\vol_experiment.py          # the rejected volatility-model variants
```

`run_backtest.py` prints the report-card metrics and writes them to `backtest/results.json`. The numbers in the table above come from that full 45-stock run. Price downloads are cached in `backtest/data/` (git-ignored). The volatility model's coefficients used by the app are hardcoded in `simulation.py` (`_VOL_MODEL`).

`backtest/health_backtest.py` is a prepared test of the health score itself. It's not run yet: it needs historical fundamentals, see above.

## How we compare

Indonesian investors already have good free tools. MARKET.EXE doesn't try to replace them; it answers a question they mostly don't.

| | Stockbit / RTI Business | TradingView / Investing.com | Simply Wall St | **MARKET.EXE** |
|---|---|---|---|---|
| Full financial statements, real-time prices, all IDX stocks | ✅ | ✅ | ✅ | Partial (via Sectors, LQ45 focus) |
| Community, news feed, broker flows | ✅ | Partial | ❌ | ❌ |
| One-number health / quality score | ❌ | ❌ | ✅ "snowflake" | ✅ HP bar, with the inputs and rules shown |
| Forward-looking 30-day price range | Analyst targets only | Volatility indicators | Analyst targets / fair value | ✅ Simulated range |
| That range checked against real outcomes | ❌ | ❌ | ❌ | ✅ 79.5% inside the 80% range |
| Risk shown in Rupiah for your amount | ❌ | ❌ | ❌ | ✅ Position risk calculator |
| Known dividends built into the forecast | ❌ | ❌ | ❌ | ✅ |
| Says openly what it can't predict | — | — | — | ✅ Report card |

**Why the gap exists:** in the US, options prices give investors the market's own expected range for free. IDX has no liquid options market, so Indonesian investors don't get that number. MARKET.EXE estimates it from each stock's own price history and publishes how accurate the estimate has been.

**Where others are stronger:** depth (full statements, every listed stock, real-time data), community and news, and years of real users. MARKET.EXE's health score is no better proven than a snowflake score as a return predictor; its advantage is transparency.

*This comparison reflects the tools' commonly known free features as of October 2026; features change, so check each tool for its current offering.*

## API

Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). They're served locally, with no CDN needed.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/api/screen?index=LQ45&limit=50` | Score and rank an index |
| GET | `/api/company/{symbol}` | Score one company, e.g. `BBCA` |
| GET | `/api/heatmap?index=LQ45` | Regime distribution per sector |
| POST | `/api/simulate/{symbol}?runs=500&days=30` | 30-day scenario range |
| POST | `/api/auth/register`, `/api/auth/login` | User accounts, returns a bearer token |
| GET | `/api/auth/me` | Current user |
| GET / DELETE | `/api/history[/{id}]` | The user's company and simulation history |
| GET / PUT / DELETE | `/api/pins[/{symbol}]` | The user's pinned stocks |
| POST | `/api/admin/login` | Admin token for admin-only routes |

**Access:**
- **Public:** the data routes, so no account is needed to browse.
- **Account required:** history and pins.
- **Admin password (`APP_PASSWORD`):** routes marked `admin_only`.

## Sectors API credits

| Action | Credits | Notes |
|---|---|---|
| Screener / heatmap load | 1 | One structured screener call |
| Company page | 4 | Company report with 4 sections |
| Run simulation | 6 | Company report (4) + 90-day daily prices (1) + corporate actions (1). Only 2 if the company page was just opened, since the report is then cached |

Every response is cached in the backend for `CACHE_TTL_SECONDS` (default 15 minutes), so repeat views are free. The cache is cleared when the backend restarts.

## Configuration (`backend/.env`)

| Key | Purpose |
|---|---|
| `SECTORS_API_KEY` | **Required.** Your Sectors API key |
| `SECTORS_BASE_URL` | Default `https://api.sectors.app/v2` |
| `CACHE_TTL_SECONDS` | Response cache lifetime |
| `ALLOWED_ORIGINS` | CORS origins allowed to call the API |
| `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` | Per-IP rate limit |
| `APP_PASSWORD` | Admin password; leave empty to disable admin login |
| `AUTH_SECRET` | Token signing key; set it so logins survive restarts |
| `AUTH_TOKEN_TTL_SECONDS`, `LOGIN_MAX_FAILURES`, `LOGIN_WINDOW_SECONDS` | Token lifetime and brute-force guard |
| `USERS_DB_PATH` | SQLite file for user accounts (created automatically) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Optional. Turn on history and pins |

**Setting up history and pins:**
1. Run `backend/supabase/schema.sql` in the Supabase SQL editor.
2. Add the project URL and a **secret** key (`sb_secret_...`) to `.env`.
3. Check the setup with `.\.venv\Scripts\python.exe check_supabase.py`.

Keep the Supabase key server-side only.

Never commit `.env`. It's git-ignored, and only `.env.example` is tracked. `users.db` is also git-ignored.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe test_offline.py      # scoring + simulation
.\.venv\Scripts\python.exe test_simulation.py   # volatility model, dividends, route fallbacks
.\.venv\Scripts\python.exe test_auth.py         # also: test_users.py, test_history.py, test_pins.py

cd ..\frontend
npm run test     # vitest
npm run build    # typecheck + production build
```

The backend tests replace Sectors and Supabase with fakes, so they need no API key and spend no credits.

## Deploying

`run.bat` is for local development only. For a deployed version:

- **Backend:**
  - start it with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, without `--reload`;
  - set the `.env` values as the host's environment variables;
  - serve it over HTTPS.
- **Frontend:**
  - build it with `npm run build` and host `frontend/dist`;
  - set `VITE_API_BASE` to the backend URL;
  - add the frontend's domain to `ALLOWED_ORIGINS`.

The data routes are public, so the per-IP rate limit is the only thing protecting your Sectors credits. The rate limiter and the response cache live in memory: they apply to a single instance and reset when it restarts.
