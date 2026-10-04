# MARKET.EXE — Frontend

React + Vite + TypeScript UI for the MARKET.EXE backend. It only fetches and
displays backend data; no scores are computed client-side.

## Run

```powershell
cd frontend
npm install        # or: bun install
npm run dev        # http://127.0.0.1:5173, proxies /api -> http://127.0.0.1:8000
```

Start the backend first (see ../README.md).

| Script | Purpose |
|---|---|
| `npm run dev` | dev server with `/api` proxy |
| `npm run build` | typecheck + production build to `dist/` |
| `npm run test` | unit tests (vitest) |

For a deployed build served from another origin, set `VITE_API_BASE`
(e.g. `https://api.example.com`) and add that frontend origin to the backend's
`ALLOWED_ORIGINS`.

## Display rules (not scoring)

- A sector is "under stress" on the heatmap when `stressed_pct >= 50`.
- Momentum is shown as N/A when `momentum === 10` and `confidence < 0.6`.
- Debt gets a bank note when `sector` matches `/financ|bank/i`.
