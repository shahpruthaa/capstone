# NSE Atlas

Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.

## Repository Layout

- `src/`: React + Vite frontend
- `apps/api/`: FastAPI backend, quant engine, ingestion, and model services
- `docs/`: project architecture, plan, and proof assumptions
- `scripts/`: smoke and acceptance helpers
- `infra/docker/`: container images and compose support

## Current Product Surface

Main tabs in the web app:

- `Overview`
- `Market`
- `Portfolio`
- `Trade Ideas`
- `Backtest`
- `Compare`

Portfolio workspace modes:

- `Build Portfolio`
- `Analyze Holdings`

Removed product areas (not in current UI):

- AI chat tab/panel
- events tab
- rebalance tab

## Backend Route Surface

Core routes currently mounted via `apps/api/app/api/router.py`:

- health
- portfolio generation + mandate questionnaire
- holdings analysis
- backtests
- benchmarks summary + compare
- market data summary + regime + ingestions
- model overview
- observability KPIs
- market-context news
- stock detail
- trade ideas list + screening + symbol detail

## Active API Endpoints

| Method | Endpoint                                  | Purpose                                 |
| ------ | ----------------------------------------- | --------------------------------------- |
| `GET`  | `/healthz`                                | Liveness check                          |
| `GET`  | `/api/v1/models/current`                  | Current model overview/runtime state    |
| `GET`  | `/api/v1/portfolio/mandate/questionnaire` | Mandate defaults/options                |
| `POST` | `/api/v1/portfolio/generate`              | Portfolio generation                    |
| `POST` | `/api/v1/analysis/portfolio`              | Holdings analysis                       |
| `POST` | `/api/v1/backtests/run`                   | Run backtest                            |
| `GET`  | `/api/v1/backtests/{run_id}`              | Fetch saved backtest                    |
| `GET`  | `/api/v1/benchmarks/summary`              | Benchmark summary                       |
| `POST` | `/api/v1/benchmarks/compare`              | Benchmark compare workflow              |
| `GET`  | `/api/v1/market-data/summary`             | Local data coverage + session status    |
| `GET`  | `/api/v1/market-data/regime`              | Market dashboard/regime                 |
| `POST` | `/api/v1/market-data/ingestions/*`        | Ingestion triggers                      |
| `GET`  | `/api/v1/news/market-context`             | Market context/news summary             |
| `GET`  | `/api/v1/observability/kpis`              | System/ops KPIs                         |
| `GET`  | `/api/v1/trade-ideas`                     | Trade idea list response                |
| `POST` | `/api/v1/trade-ideas/screen`              | Trade idea screen with holdings context |
| `GET`  | `/api/v1/trade-ideas/{symbol}`            | Single-symbol trade idea                |
| `GET`  | `/api/v1/stock/{symbol}`                  | Stock detail explanation payload        |

## Runtime Behavior (Current)

- Portfolio generation and analysis are backend-first and use the DB quant engine.
- Ensemble-related logic in the core engine path is preserved from `kairavee-improv`.
- Scheduler startup/shutdown is wired into FastAPI lifecycle (`APP_SCHEDULER_ENABLED` controlled).
- Market calendar logic is used for trading-day handling in ingestion.
- Backtest UI uses backend historical replay APIs, not the old synthetic-only path.

## Local Setup

### Frontend

```bash
npm install
npm run dev
```

### Backend (Windows)

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

### Backend (macOS/Linux)

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Docker Services

```bash
docker compose up -d postgres redis api
```

## Validation

Recommended checks:

- `npm run build`
- `npm run lint`
- `python -m py_compile apps/api/app/services/db_quant_engine.py`
- `python -m py_compile apps/api/app/services/decision_engine.py`
- `python -m py_compile apps/api/app/services/scheduler.py`

## Notes

- This repository is for research workflows, not order execution.
- PostgreSQL is required for live generation/analysis/backtests.
- Some benchmark and market views are proxy-based by design and explicitly labeled.
