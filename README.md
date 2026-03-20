# NSE AI Portfolio Manager

This repository now runs fully locally as a Vite + React application. The previous Google AI Studio / Gemini dependency has been removed and replaced with a local advisory engine for portfolio commentary, rebalancing suggestions, and chat responses.

The current codebase includes:
- Risk-based portfolio generation for NSE-oriented stock baskets
- Portfolio analysis with sector concentration and correlation checks
- A simulated backtesting engine with Indian market cost and tax hooks
- Benchmark comparison views for quant and index-style strategies
- A local strategy assistant that runs without external APIs

## Run Locally

**Prerequisites:** Node.js 20+

1. Install dependencies:
   `npm install`
2. Run the app:
   `npm run dev`
3. Open:
   `http://localhost:3000`

## Notes

- No API keys are required for the current local-only build.
- Market data, optimizer logic, and benchmark results are still prototype-grade and should be upgraded before production use.
- The detailed product and engineering roadmap lives in `docs/technical-plan.md`.
- The target system design lives in `docs/architecture.md`.

## Backend Scaffold

The repository now includes a FastAPI scaffold in `apps/api` plus Docker Compose for:
- `web` on `http://localhost:3000`
- `api` on `http://localhost:8000`
- `postgres` on `localhost:5433`
- `redis` on `localhost:6379`

Start the full local stack with:

`docker compose up --build`

The first API routes are:
- `GET /healthz`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

## Database And Ingestion

Alembic files now live in `apps/api/alembic`.

Typical local flow:

1. Start infrastructure:
   `docker compose up --build`
2. Run migrations from the API folder:
   `cd apps/api`
   `alembic upgrade head`
   Or run them inside Docker:
   `docker compose exec api alembic upgrade head`
3. Ingest the first NSE bhavcopy slice:
   `python scripts/ingest_nse_bhavcopy.py --start-date 2025-01-01 --end-date 2025-01-10`
   Or inside Docker:
   `docker compose exec api python scripts/ingest_nse_bhavcopy.py --start-date 2025-01-01 --end-date 2025-01-10`

The bhavcopy pipeline stores raw archives under `data/raw/nse/cm/...`, parses daily CSV payloads, and upserts `instruments` plus `daily_bars` into PostgreSQL/Timescale.
