# NSE AI Portfolio Manager

Local-first AI-assisted portfolio management platform for NSE-oriented investing. This project combines a React/Vite analytics UI with a FastAPI quant backend, PostgreSQL + TimescaleDB market storage, NSE bhavcopy ingestion, historical backtesting, benchmark comparison, and a local explainability layer.

The current version is a working engineering prototype with a real backend/data path. It is no longer dependent on Google AI Studio or Gemini and is designed to run entirely on your machine.

## What This Project Does

This repository currently contains:

- A portfolio generation workspace with three risk modes:
  - `Ultra-Low / Capital Preservation`
  - `Balanced / Moderate Risk`
  - `High Risk / Aggressive Growth`
- A holdings analysis workspace for:
  - current portfolio value
  - sector concentration
  - diversification scoring
  - empirical correlation warnings
  - rebalance suggestions
- A backtest workspace for:
  - historical replay from stored daily market data
  - stop-loss / take-profit logic
  - transaction cost drag
  - Indian tax drag approximation
- A benchmark comparison workspace for:
  - AI portfolio vs benchmark-style strategies
  - projected growth comparison
  - risk-adjusted return summaries
- A local advisory/chat layer for explaining portfolio outputs in natural language
- A FastAPI backend that serves quant results to the UI
- A PostgreSQL + TimescaleDB store for instruments, bars, ingestion runs, generated portfolios, and backtest runs
- An NSE bhavcopy ingestion pipeline with local raw-file caching, instrument enrichment, and CLI progress bar output
- A constrained allocator over a shrinkage covariance risk model for backend-generated portfolios

## Current Status

This repo is no longer just a UI mockup. It now has:

- Completed:
  - React UI shell
  - local-only runtime
  - Dockerized frontend/backend/database stack
  - FastAPI API surface
  - PostgreSQL + TimescaleDB schema
  - Alembic migrations
  - NSE bhavcopy ingestion pipeline
  - instrument master enrichment hooks
  - DB-backed portfolio generation
  - DB-backed benchmark summary
  - DB-backed historical backtest path
  - UI loading/fallback/error notices

- Partially complete:
  - risk model and constrained optimizer
  - holdings analyzer and rebalance engine
  - benchmark engine
  - tax and fee realism
  - historical simulation fidelity

- Not complete yet:
  - corporate-action-adjusted pricing
  - live market feed ingestion
  - broker integrations
  - authentication and user accounts
  - CSV/broker holdings import
  - regime overlays
  - production compliance/audit features

## Tech Stack

### Frontend

- React 19
- Vite
- TypeScript
- Recharts
- Lucide React

### Backend

- Python 3.12
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- psycopg v3

### Data and Infrastructure

- PostgreSQL
- TimescaleDB
- Redis
- Docker Compose

### Local AI / Explanation Layer

- Local deterministic advisor in the frontend
- No hosted LLM dependency required
- Optional future path for local Ollama-based explanations

## Project Structure

```text
nse-ai-portfolio-manager/
  apps/
    api/
      app/
        api/            # FastAPI routes
        core/           # settings/config
        db/             # SQLAlchemy setup
        ingestion/      # NSE bhavcopy pipeline
        models/         # ORM models
        schemas/        # Pydantic contracts
        services/       # quant engine + enrichment services
      alembic/          # migrations
      scripts/          # CLI scripts
  docs/
    architecture.md     # target architecture
    technical-plan.md   # implementation roadmap
  infra/
    docker/             # Dockerfiles
  src/
    components/         # UI tabs and widgets
    data/               # static stock metadata used by the frontend
    services/           # frontend API adapters + local fallback logic
  data/
    raw/                # cached NSE archives
```

## Implemented Features

### 1. Portfolio Generation

The `Generate` tab supports:

- risk-mode-based portfolio generation
- backend-first portfolio generation with frontend fallback
- backend model notes shown in the UI
- local explainability panel
- transaction cost summary

Current backend logic:

- loads candidate instruments from the database
- builds aligned daily return series
- estimates expected returns
- builds a shrinkage covariance matrix
- runs a constrained long-only allocator with:
  - full investment
  - per-asset caps
  - per-sector caps

### 2. Portfolio Analysis

The `Analyze` tab supports:

- manual holdings entry
- current portfolio valuation
- sector exposure view
- diversification scoring
- empirical correlation warnings
- rebalance action suggestions
- local rebalancing commentary

Current backend logic:

- uses DB-backed latest close prices
- computes weighted beta proxy
- computes sector weights
- measures pairwise return correlation
- compares current portfolio against target risk-mode sector budgets

### 3. Backtesting

The `Backtest` tab supports:

- selecting a historical range
- configuring stop-loss, take-profit, and rebalance cadence
- viewing equity curve vs benchmark
- viewing tax drag and cost drag
- inspecting core performance metrics

Current backend backtest logic:

- reconstructs a strategy portfolio from the selected risk mode
- replays using stored daily closes
- triggers stop-loss / take-profit exits
- supports periodic rebalancing
- applies brokerage, STT, stamp duty, GST, and slippage approximations
- tracks STCG/LTCG buckets at a simplified level

### 4. Benchmark Comparison

The `Compare` tab supports:

- backend-first benchmark comparison with frontend fallback
- strategy cards
- return vs drawdown comparison
- Sharpe comparison
- projected growth chart

Current backend benchmark logic:

- `NSE AI Portfolio`
- `Nifty 50` proxy
- `Nifty 500` proxy
- `Momentum Basket`
- `AMC Multi Factor` proxy

### 5. Local Assistant

The app includes a local strategy assistant for:

- portfolio commentary
- rebalancing explanation
- chat-style responses over current UI state

This layer is explanatory only. It is not the authoritative portfolio decision engine.

## Backend APIs

Current API routes:

- `GET /`
- `GET /healthz`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

Swagger docs:

- [http://localhost:8000/docs](http://localhost:8000/docs)

## Database and Data Model

Current persisted entities include:

- `instruments`
- `daily_bars`
- `ingestion_runs`
- `generated_portfolio_runs`
- `generated_portfolio_allocations`
- `backtest_runs`

TimescaleDB is configured for the `daily_bars` time-series table.

Instrument enrichment currently adds:

- sector
- instrument type
- market-cap bucket

for a curated subset of important symbols and ETFs.

## NSE Ingestion Pipeline

Current ingestion source:

- NSE CM bhavcopy archive files

What the pipeline does:

- downloads daily zip archives
- caches raw files to `data/raw/nse/cm/...`
- parses CSV payloads
- normalizes symbol / series / ISIN / prices / traded values
- reuses instruments by `symbol + series` or `isin`
- updates instrument identity if the ISIN matches but the symbol changes
- upserts daily bars
- records ingestion-run metadata
- prints a live CLI progress bar

Important operational note:

- The backend needs enough historical bars before the DB-backed UI paths stop falling back to local mock logic.
- Very small ingestion windows like `2025-01-01` through `2025-01-10` are not enough for the current optimizer and benchmark engine.

## How To Run

### Option A: Frontend only

Good for UI exploration without the backend.

```bash
npm install
npm run dev
```

Open:

- [http://localhost:3000](http://localhost:3000)

### Option B: Full local stack

```bash
docker compose up -d --build
```

Services:

- frontend: [http://localhost:3000](http://localhost:3000)
- backend: [http://localhost:8000](http://localhost:8000)
- postgres: `localhost:5433`
- redis: `localhost:6379`

## Local Setup Flow

### 1. Start the stack

```bash
docker compose up -d --build
```

### 2. Apply migrations

```bash
docker compose exec api alembic upgrade head
```

### 3. Ingest enough historical data

Recommended:

```bash
docker compose exec api python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-03-15
```

### 4. Open the UI

- [http://localhost:3000](http://localhost:3000)

## Useful Commands

### Frontend

```bash
npm run dev
npm run lint
npm run build
```

### Backend

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-03-15
```

### Database checks

```bash
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from instruments;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from daily_bars;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select min(trade_date), max(trade_date) from daily_bars;"
```

## Development Phases and Completion Status

| Phase | Scope | Status | Notes |
| --- | --- | --- | --- |
| Phase 0 | Frontend shell and UX prototype | Complete | Generate, Analyze, Backtest, Compare tabs are live |
| Phase 1 | Local-first backend foundation | Complete | FastAPI, Docker, PostgreSQL, Redis, Alembic all present |
| Phase 2 | Historical data ingestion | Complete | NSE bhavcopy ingestion works with caching and progress reporting |
| Phase 3 | Quant allocator | Partial | Shrinkage covariance + constrained allocator implemented; factor model still basic |
| Phase 4 | Analyzer and rebalance engine | Partial | DB-backed analytics and rebalance suggestions exist; target model still simplified |
| Phase 5 | Historical simulation realism | Partial | Daily-close replay works; intraday stop execution and corp-action adjustments are still pending |
| Phase 6 | Benchmark and research engine | Partial | Backend benchmark summaries exist; benchmark methodology is still proxy-based |
| Phase 7 | Productization and governance | Not started | auth, audit trails, broker integration, compliance rails still pending |

## What Is Complete Right Now

- Local-only runtime
- Google AI Studio dependency removed
- React UI shell
- Typed frontend-to-backend API wiring
- Dockerized local stack
- Alembic migrations
- Timescale-backed time-series table
- NSE bhavcopy ingestion with raw caching
- Instrument enrichment hooks
- DB-backed generator
- DB-backed analysis
- DB-backed backtesting
- DB-backed benchmarking
- UI notices for loading / error / fallback states
- CLI progress bar for ingestion

## What Is Still Approximate

- Expected return model
- Tax model detail
- Fee table detail by effective date
- Benchmark construction
- Rebalance policy
- Corporate-action adjustment
- Sector and factor models
- Live market behavior

## Known Limitations

- The current engine needs sufficient historical bars in the database to avoid frontend fallback behavior.
- Backtest execution uses daily closes, not intraday trigger modeling.
- Benchmarks are still strategy proxies, not full institutional benchmark replications.
- The local advisory layer explains results but does not make authoritative investment decisions.
- Some legacy scaffold files remain in the repo for reference, such as [mock_quant_engine.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/mock_quant_engine.py), but they are not the active backend path.

## AI Context Export Script

This repository includes a context export utility for AI workflows where the model cannot access the project folder directly.

Script:

- [generate_ai_context.py](C:/Users/pruth/nse-ai-portfolio-manager/scripts/generate_ai_context.py)

What it does:

- builds a directory tree
- lists included and skipped files
- captures full contents of important text/code/config files
- skips heavy/generated directories by default
- writes everything into a single `.txt` file suitable for sharing with external AI tools

Example:

```bash
python scripts/generate_ai_context.py
```

Custom output:

```bash
python scripts/generate_ai_context.py --output project_context.txt
```

## Documentation

Additional project docs:

- [architecture.md](C:/Users/pruth/nse-ai-portfolio-manager/docs/architecture.md)
- [technical-plan.md](C:/Users/pruth/nse-ai-portfolio-manager/docs/technical-plan.md)
- [apps/api/README.md](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/README.md)

## Disclaimer

This project is for education, prototyping, and research workflows. It is not investment advice, not a broker, and not a substitute for a SEBI-registered advisor. Current tax, fee, and execution logic are engineering approximations and must be validated before any production or real-money use.
