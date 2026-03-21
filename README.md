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
  - factor exposure inspection
  - optimizer-aligned rebalance suggestions
- A backtest workspace for:
  - historical replay from stored daily OHLC market data
  - stop-loss / take-profit logic with gap-aware fills
  - dated fee schedules and liquidity-aware slippage
  - FIFO tax-lot realization with FY-wise LTCG exemption handling
  - corporate-action-aware price adjustment and dividend cash credits when actions are loaded
- A benchmark comparison workspace for:
  - AI portfolio vs benchmark-style strategies
  - factor and broad-market proxy comparisons
  - projected growth comparison
  - risk-adjusted return summaries
- A local advisory/chat layer for explaining portfolio outputs in natural language
- A FastAPI backend that serves quant results to the UI
- A PostgreSQL + TimescaleDB store for instruments, bars, ingestion runs, generated portfolios, and backtest runs
- An NSE bhavcopy ingestion pipeline with local raw-file caching, instrument enrichment, and CLI progress bar output
- A corporate-actions schema plus CSV import path for splits, bonuses, and dividends
- A constrained allocator over a shrinkage covariance risk model for backend-generated portfolios

## Current Status

This repo has:

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
  - factor-aware expected return model
  - dated delivery-equity fee engine
  - FIFO tax-lot engine for delivery-equity backtests
  - drift-threshold rebalance policy
  - DB-backed benchmark summary
  - DB-backed historical backtest path
  - UI loading/fallback/error notices

- Partially complete:
  - benchmark engine
  - live market behavior
  - sector and factor model depth

- Not complete yet:
  - live market feed ingestion
  - broker integrations
  - authentication and user accounts
  - CSV/broker holdings import
  - benchmark constituent ingestion from official index files
  - richer fundamentals-driven factor data
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
- builds aligned total-return series
- estimates expected returns from momentum, quality proxy, low-volatility, liquidity, sector strength, size, and beta discipline
- builds a shrinkage covariance matrix
- runs a constrained long-only allocator with:
  - full investment
  - per-asset caps
  - per-sector caps

### 1A. Expected Return Model Specification

For the current supported scope, the expected return model is complete and implemented.

Inputs:

- adjusted total-return history
- annualized aligned return mean
- factor z-scores:
  - `momentum`
  - `quality`
  - `low_vol`
  - `liquidity`
  - `sector_strength`
  - `size`
  - `beta`
- a simple regime overlay

Factor construction:

- `momentum = 0.20 * 1M + 0.35 * 3M + 0.45 * 6M`
- `quality = annual_return - 0.70 * downside_vol - 0.40 * max_drawdown + beta_discipline`
- `low_vol = -annual_volatility`
- `liquidity = sqrt(avg_traded_value)`
- `sector_strength = stock_momentum - sector_average_momentum`
- `size = {Large: 1, Mid: 0, Small: -1, Unknown: -0.25}`
- `beta = beta_proxy - 1`

Risk-mode return blend:

- `ULTRA_LOW`
  - regime base return
  - `0.30 * annual_mean`
  - `0.028 * factor_alpha`
  - defensive / ETF bonus
- `MODERATE`
  - regime base return
  - `0.36 * annual_mean`
  - `0.030 * factor_alpha`
- `HIGH`
  - regime base return
  - regime risk-on bonus
  - `0.42 * annual_mean`
  - `0.035 * factor_alpha`
  - cyclical-sector bonus

Stability controls:

- penalizes unstable beta drift away from `1.0`
- clamps expected returns into a bounded engineering range before optimization

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
- computes factor exposures
- compares current holdings against the optimizer-generated target portfolio for the selected risk mode

### 2A. Rebalance Policy Specification

For the current supported scope, rebalance policy is complete and implemented.

Review cadence:

- `MONTHLY = 21` trading-day review interval
- `QUARTERLY = 63` trading-day review interval
- `ANNUALLY = 252` trading-day review interval
- `NONE = no scheduled rebalance`

Risk-mode thresholds:

| Risk Mode | Drift Threshold | Minimum Trade Weight | Cooldown After Exit |
| --- | --- | --- | --- |
| `ULTRA_LOW` | `6.0%` | `3.0%` | `5 days` |
| `MODERATE` | `4.0%` | `2.5%` | `7 days` |
| `HIGH` | `3.0%` | `2.0%` | `10 days` |

Execution rules:

- compare current holdings to the latest optimizer-generated target portfolio
- trade only if:
  - absolute drift exceeds the risk-mode threshold
  - trade size exceeds the minimum trade budget
- sell first when over target
- buy only if cash is available and the symbol is not still in cooldown after a prior exit

### 3. Backtesting

The `Backtest` tab supports:

- selecting a historical range
- configuring stop-loss, take-profit, and rebalance cadence
- viewing equity curve vs benchmark
- viewing tax drag and cost drag
- inspecting core performance metrics

Current backend backtest logic:

- reconstructs a strategy portfolio from the selected risk mode
- replays using stored adjusted daily OHLC bars
- triggers stop-loss / take-profit exits with gap-aware fills
- supports drift-threshold-based periodic rebalancing
- applies brokerage, STT, stamp duty, exchange transaction fees, SEBI fees, GST, and liquidity-aware slippage using versioned schedules
- tracks FIFO tax lots, STCG/LTCG realization, and cess at a detailed engineering level

### 3A. Tax Model Specification

For the current supported scope, the delivery-equity tax model is complete and implemented.

Lot accounting:

- FIFO tax lots per symbol
- realized gains are bucketed by:
  - financial year
  - holding period
  - effective tax schedule

Holding-period rules:

- `STCG`: holding period `< 365 days`
- `LTCG`: holding period `>= 365 days`

Implemented tax schedules:

| Effective From | STCG | LTCG | LTCG Exemption | Cess | Notes |
| --- | --- | --- | --- | --- | --- |
| `2020-07-01` | `15%` | `10%` | `Rs 1,00,000` | `4%` | pre-Budget-2024 listed-equity schedule |
| `2024-07-23` | `20%` | `12.5%` | `Rs 1,25,000` | `4%` | Budget-2024 listed-equity schedule |

Computation flow:

- aggregate STCG by fiscal year and schedule
- apply STCG only to positive net STCG
- aggregate LTCG separately by fiscal year
- net positive and negative LTCG within the same fiscal-year schedule bucket
- apply the LTCG exemption once per fiscal year
- apply cess on computed base tax

Output fields surfaced in the app:

- `stcg_gain`
- `ltcg_gain`
- `stcg_tax`
- `ltcg_tax`
- `cess_tax`
- `total_tax`

### 3B. Fee Model Specification

For the current supported scope, the dated delivery-equity fee model is complete and implemented.

Per-trade fee formula:

- `brokerage = min(turnover * brokerage_rate, max_brokerage_per_order)`
- `stt = turnover * stt_rate(side)`
- `stamp_duty = turnover * stamp_duty_buy_rate` on buy only
- `exchange_txn = turnover * exchange_txn_rate`
- `sebi_fee = turnover * sebi_fee_rate`
- `gst = (brokerage + exchange_txn + sebi_fee) * gst_rate`
- `slippage = turnover * liquidity_adjusted_slippage_rate`
- `total_costs = sum(all components)`

Implemented fee schedules:

| Effective From | Brokerage | Max Brokerage | STT Buy | STT Sell | Exchange Txn | SEBI | Stamp Duty Buy | GST |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `2020-07-01` | `0.03%` | `Rs 20` | `0.10%` | `0.10%` | `0.00297%` | `0.00010%` | `0.015%` | `18%` |
| `2024-07-23` | `0.03%` | `Rs 20` | `0.10%` | `0.10%` | `0.00297%` | `0.00010%` | `0.015%` | `18%` |

Slippage model:

- liquidity participation based
- volatility loaded
- capped to avoid unrealistic daily-bar execution assumptions

### 4. Benchmark Comparison

The `Compare` tab supports:

- backend-first benchmark comparison with frontend fallback
- strategy cards
- return vs drawdown comparison
- Sharpe comparison
- projected growth chart

Current backend benchmark logic:

- `NSE AI Portfolio`
- `Nifty 50 Proxy`
- `Nifty 500 Proxy`
- `Momentum Factor`
- `Quality Factor`
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
- `corporate_actions`
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
docker compose exec api python scripts/import_corporate_actions.py --csv /path/to/corporate_actions.csv
```

### Database checks

```bash
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from instruments;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from daily_bars;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select min(trade_date), max(trade_date) from daily_bars;"
```

## Development Phases and Completion Status

| Phase   | Scope                           | Status                     | Notes                                                                                                                                |
| ------- | ------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 0 | Frontend shell and UX prototype | Complete                   | Generate, Analyze, Backtest, Compare tabs are live                                                                                   |
| Phase 1 | Local-first backend foundation  | Complete                   | FastAPI, Docker, PostgreSQL, Redis, Alembic all present                                                                              |
| Phase 2 | Historical data ingestion       | Complete                   | NSE bhavcopy ingestion works with caching and progress reporting                                                                     |
| Phase 3 | Quant allocator                 | Complete for current scope | Factor-aware expected return model, shrinkage covariance, and constrained allocator are live for the local research stack           |
| Phase 4 | Analyzer and rebalance engine   | Complete for current scope | DB-backed analytics, factor exposures, and target-diff rebalance actions are live                                                   |
| Phase 5 | Historical simulation realism   | Partial                    | OHLC replay, gap-aware stops, FIFO tax lots, dated fees, and corporate-action support are live; no intraday/tick engine yet        |
| Phase 6 | Benchmark and research engine   | Partial                    | Backend benchmark summaries exist with factor and broad-market proxies; official constituent replication is still pending           |
| Phase 7 | Productization and governance   | Not started                | auth, audit trails, broker integration, compliance rails still pending                                                               |

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
- Factor-aware expected return model
- Delivery-equity tax model with FIFO lots and cess
- Dated delivery-equity fee schedule resolution
- Drift-threshold rebalance policy
- DB-backed generator
- DB-backed analysis
- DB-backed backtesting
- DB-backed benchmarking
- UI notices for loading / error / fallback states
- CLI progress bar for ingestion

## What Is Still Approximate

| Area                               | Status          | Current implementation                                                                 |
| ---------------------------------- | --------------- | -------------------------------------------------------------------------------------- |
| Expected return model              | Complete for current scope | factor-aware expected return blend over total-return history with regime tilt            |
| Tax model detail                   | Complete for current scope | FIFO tax lots, FY-wise LTCG exemption, STCG/LTCG + cess                                 |
| Fee table detail by effective date | Complete for current scope | dated cash-equity fee schedule with brokerage/STT/stamp/exchange/SEBI/GST/slippage      |
| Benchmark construction             | Partial         | locally computed proxy benchmarks, not official constituent files                      |
| Rebalance policy                   | Complete for current scope | drift-threshold plus cadence-driven rebalance logic by risk mode                        |
| Corporate-action adjustment        | Partial         | schema, import path, price adjustment, and dividend credits exist; data must be loaded |
| Sector and factor models           | Partial         | price-and-liquidity-based factors only; no licensed fundamentals yet                   |
| Live market behavior               | Partial         | daily OHLC, gap-aware fills, liquidity slippage; no intraday order-book simulation     |

## Known Limitations

- The current engine needs sufficient historical bars in the database to avoid frontend fallback behavior.
- Backtest execution is daily-bar based, not tick or intraday order-book based.
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
