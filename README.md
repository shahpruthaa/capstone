# NSE Atlas

Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.

## What This Repo Contains

- `src/`: React + Vite frontend
- `apps/api/`: FastAPI backend, quant engine, model runtime, and artifacts
- `docs/`: architecture and technical notes
- `scripts/`: local validation and maintenance helpers
- `infra/docker/`: Docker support

## Product Surface

The current app shell exposes these primary tabs:

- `Overview`
- `Market`
- `Portfolio`
- `Trade Ideas`
- `Backtest`
- `Compare`

The `Portfolio` workspace has two flows:

- `Build Portfolio`
- `Analyze Holdings`

Removed from the current product:

- chatbot / AI chat
- events tab
- rebalance portfolio tab
- generate AI analysis panel

## Frontend Highlights

- `src/App.tsx` owns the top-level shell and tab routing.
- `src/components/GenerateTab.tsx` builds portfolios from mandate inputs.
- `src/components/AnalyzeTab.tsx` analyzes pasted or manually entered holdings.
- `src/components/BacktestTab.tsx` runs historical replay with costs and taxes.
- `src/components/CompareTab.tsx` compares strategies and benchmarks.
- `src/services/backendApi.ts` is the shared frontend API adapter.

## Backend Highlights

- `apps/api/app/api/router.py` wires the active API routes.
- `apps/api/app/services/db_quant_engine.py` handles portfolio generation, holdings analysis, and backtests.
- `apps/api/app/services/model_runtime.py` reports ensemble readiness and artifact status.
- `apps/api/app/services/model_overview.py` adds live current-signal and validation summaries for the Overview tab.
- `apps/api/app/services/ensemble_scorer.py` combines component model predictions.
- `apps/api/app/api/routes/stock_detail.py` exposes stock-level analysis surfaces.

## Active API Endpoints

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `GET` | `/api/v1/models/current` | Runtime readiness and model status |
| `GET` | `/api/v1/market-data/summary` | Local market data coverage |
| `POST` | `/api/v1/portfolio/generate` | Generate a portfolio |
| `POST` | `/api/v1/analysis/portfolio` | Analyze holdings |
| `POST` | `/api/v1/backtests/run` | Run a backtest |
| `GET` | `/api/v1/benchmarks/summary` | Benchmark comparison summary |
| `GET` | `/api/v1/trade-ideas` | Trade-idea shortlist |
| `GET` | `/api/v1/stock/...` | Stock detail surfaces |

## Runtime Notes

- Portfolio generation is ensemble-first and no longer silently falls back during generation.
- Mandate horizon controls portfolio decision logic, not model feature history depth.
- Holdings analysis has a backend-first path with a local fallback when the API is unavailable.
- Portfolio construction now applies stronger diversification controls across names and sectors.
- Market session state is now derived from an NSE holiday calendar plus IST trading hours instead of static UI text.
- Backtests in the active UI use the backend historical replay endpoint rather than a synthetic GBM simulation path.

## Local Setup

### Frontend

```bash
npm install
npm run dev
```

### Backend

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker compose up -d api postgres redis
```

## Validation

Useful local checks:

- `npm run build`
- `python -m py_compile apps/api/app/services/db_quant_engine.py`
- `python -m py_compile apps/api/app/services/mandate.py`
- `python -m py_compile apps/api/app/services/ensemble_scorer.py`

## Notes

- The app is designed for local-first research workflows, not broker execution.
- PostgreSQL availability is still required for live backend generation and holdings analysis.
- Benchmark reconstruction remains partially proxy-based for demo continuity.
