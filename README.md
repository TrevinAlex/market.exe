# MARKET.EXE — Backend

IDX stock **health regime scanner** + **agent-based scenario simulator** for the
Sectors Hackathon 2026 (Track 3 · Market Intelligence).

## What it does

1. **Scoring engine** (`app/core/scoring.py`) — pulls raw fields from the Sectors
   API and derives a 0–100 composite health score across 5 dimensions
   (valuation, momentum, debt, quality, profitability), then maps it to a market
   regime: `Accumulation / Recovery / Distribution / Stress`. These derived
   signals do **not** exist in the raw API — this is the Track 3 qualifier.
2. **Sector heatmap** — aggregates regimes per sector into a macro signal
   (e.g. "68% of Banking is in Distribution").
3. **ABM simulator** (`app/core/simulation.py`) — 1000 agents whose behavioural
   mix is **calibrated from the health sub-scores** (not random) trade the stock
   over N days; a Monte Carlo of 500 runs yields a price-outcome distribution.

## Setup

```powershell
cd C:\Users\Trevin\Downloads\market.exe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and paste your Sectors hackathon API key into SECTORS_API_KEY
```

## Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open interactive docs at http://127.0.0.1:8000/docs

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/api/screen?index=LQ45&limit=30` | score & rank companies |
| GET | `/api/company/{symbol}` | score one company (e.g. BBCA) |
| GET | `/api/heatmap?index=LQ45` | sector regime distribution |
| POST | `/api/simulate/{symbol}?runs=500&days=30` | ABM Monte Carlo scenario |

## API credits

The screener endpoint costs **1 credit per structured call**; responses are
cached in-process for `CACHE_TTL_SECONDS` (default 15 min) so dev iteration does
not burn the 1,000-credit grant. The simulator calls **no API** — it is pure
numpy and runs on demand.

## Notes / where to extend

- Valuation currently scores against an absolute PE band because peer averages
  (`pe_peer_avg`) are not in the screener's default projection. If you add them
  via a per-symbol detailed query, switch `score_valuation` to the relative
  model described in the design.
- `score_quality` uses ROE as a proxy; the design's "cash conversion ratio"
  (`operating_cash_flow_q / earnings_mrq`) is a stronger signal — add those two
  bracketed quarterly fields to `SCORING_FIELDS` and wire a new dimension.
