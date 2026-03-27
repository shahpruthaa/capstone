# NSE AI Portfolio Manager

Local-first portfolio research platform for NSE investing. The app uses a React/Vite frontend, a FastAPI backend, PostgreSQL + TimescaleDB for market storage, NSE bhavcopy ingestion, historical backtesting with Indian market frictions, and a local LightGBM hybrid alpha model for equity expected returns.

There is no external quant API in the active path. The UI talks directly to the local FastAPI service. Portfolio generation, holdings analysis, backtests, benchmark summaries, and model status all come from the local backend.

## Current State

Implemented today:

- React UI with `Generate`, `Analyze`, `Backtest`, and `Compare` tabs
- Local FastAPI API surface
- PostgreSQL + TimescaleDB schema and Alembic migrations
- NSE bhavcopy ingestion with raw ZIP caching under `data/raw/nse/cm/...`
- Corporate-action schema and import path
- DB-backed portfolio generation with shrinkage covariance and constrained allocation
- DB-backed holdings analysis with correlation, factor exposures, and rebalance suggestions
- DB-backed backtests with gap-aware stop-loss / take-profit logic
- FIFO tax-lot engine with FY-wise LTCG exemption handling
- Dated fee engine for delivery-equity simulation
- LightGBM hybrid stack for local ML dataset build, training, inference, and artifact loading
- Model status endpoint for UI/runtime visibility
- Market-data summary endpoint for valid date-range and local readiness checks
- Benchmark provenance metadata for proxy-vs-local strategy comparisons
- Evaluation report generation under `apps/api/artifacts/reports/...`
- UI endpoint adapters verified against the live local backend

Still incomplete:

- official benchmark constituent ingestion and historical reconstitution
- live market feeds and broker connectivity
- richer fundamentals-based factors
- user auth, portfolio persistence, and audit workflows
- deeper historical cache before 2024 in the checked-in raw data set
- a standard-history LightGBM artifact with positive held-out validation metrics

## UI Endpoint Map

The frontend now uses the local backend directly through `src/services/backendApi.ts`.

- `Generate` tab
  - `GET /api/v1/models/current`
  - `POST /api/v1/portfolio/generate`
- `Analyze` tab
  - `POST /api/v1/analysis/portfolio`
- `Backtest` tab
  - `GET /api/v1/market-data/summary`
  - `GET /api/v1/models/current`
  - `POST /api/v1/backtests/run`
- `Compare` tab
  - `GET /api/v1/benchmarks/summary`
- app shell readiness panel
  - `GET /api/v1/models/current`
  - `GET /api/v1/market-data/summary`

Runtime configuration:

- frontend base URL env var: `VITE_API_BASE_URL`
- default local API target: `http://localhost:8000`
- example frontend env file: `.env.example`

## Active Model Variants

- `LIGHTGBM_HYBRID`
  - default request mode for portfolio generation and backtests
  - uses local LightGBM inference for equities when a valid artifact exists
  - blends ML annualized expected return with the rule model
  - automatically falls back to rules for ETFs or missing/invalid model scores
- `RULES`
  - deterministic factor model only
  - used automatically when no valid LightGBM artifact is available

## Tech Stack

Frontend:

- React 19
- Vite
- TypeScript
- Recharts
- Lucide React

Backend:

- Python 3.13 local venv in current setup
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- psycopg v3
- LightGBM
- pandas / numpy

Data and infrastructure:

- PostgreSQL
- TimescaleDB
- Redis
- Docker Compose

## Repository Layout

```text
apps/api/
  app/
    api/                  # FastAPI routes
    core/                 # settings/config
    db/                   # engine/session/base
    ingestion/            # NSE bhavcopy ingestion pipeline
    ml/lightgbm_alpha/    # local ML dataset / train / predict / artifacts
    models/               # ORM models
    schemas/              # Pydantic contracts
    services/             # quant engine, market rules, corporate actions
  alembic/                # migrations
  scripts/                # CLI utilities for ingestion and ML
src/
  components/             # UI tabs
  services/               # frontend API adapters and shared types
docs/
  architecture.md
  technical-plan.md
data/raw/
  nse/cm/                 # cached bhavcopy archives
```

## Main Features

### Generate

- builds risk-mode portfolios from local DB histories
- uses shrinkage covariance plus a constrained allocator
- surfaces backend notes, model source, model version, and top ML drivers

### Analyze

- values current holdings from local market data
- computes beta, diversification, correlation risk, and factor exposures
- compares current holdings to an optimizer-generated target portfolio
- returns ML scores and top drivers when the hybrid model is active

### Backtest

- replays adjusted OHLC histories from the database
- applies stop-loss / take-profit logic with gap-aware fills
- applies brokerage, STT, stamp duty, exchange transaction fees, SEBI fees, GST, and slippage
- realizes FIFO tax lots and computes STCG / LTCG / cess

### Compare

- returns backend benchmark summaries
- returns benchmark provenance fields such as `construction_method`, `is_proxy`, `source_window`, `constituent_method`, and `limitations`
- currently uses locally computed proxy portfolios, not official index constituent reconstitution

### System Readiness

- the app shell reads `models/current` and `market-data/summary`
- shows whether local market data is loaded
- shows active model version, training mode, and bootstrap-vs-standard artifact classification
- shows the active local market-data range used to constrain backtests

## Quick Start

### 1. Frontend dependencies

```bash
npm install
```

### 2. Backend Python environment

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt
```

### 3. Start database services

```bash
docker compose up -d postgres redis
```

### 4. Run migrations

```bash
cd apps/api
.venv/bin/alembic upgrade head
```

### 5. Ingest market history

Recommended minimum for the current checked-in cache:

```bash
cd apps/api
.venv/bin/python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-12-31
```

### 6. Optional but recommended: build and train the local LightGBM artifact

```bash
cd apps/api
.venv/bin/python scripts/ml/build_ml_dataset.py --start-date 2024-01-01 --end-date 2025-12-31 --max-symbols 120
.venv/bin/python scripts/ml/train_lightgbm_model.py \
  --dataset-csv artifacts/datasets/lightgbm_v1/ml_dataset.csv \
  --dataset-manifest-json artifacts/datasets/lightgbm_v1/dataset_manifest.json \
  --artifact-dir artifacts/models/lightgbm_v1
```

Notes:

- the training script automatically compresses walk-forward window sizes when the available history is shorter than the preferred 24/6/6 monthly split
- with only the current 2024+ local cache, the first artifact trains in a bootstrap mode and may be accepted with limited validation quality metadata
- once you ingest a deeper history, retrain with the longer preferred split

### 7. Start the API

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### 8. Start the web app

```bash
npm run dev
```

Open:

- UI: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

## Demo Flow

1. Start services with `docker compose up -d --build api web postgres redis`
2. Check `GET /api/v1/market-data/summary`
3. Check `GET /api/v1/models/current`
4. Generate a portfolio with `LIGHTGBM_HYBRID`
5. Analyze holdings
6. Run a backtest inside the reported market-data range
7. Open the Compare tab and review proxy labels plus benchmark construction notes

## API Routes

- `GET /`
- `GET /healthz`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `GET /api/v1/models/current`
- `GET /api/v1/market-data/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

## Local ML Workflow

Dataset builder:

- creates one row per `(symbol, decision_date)`
- uses monthly decision dates
- derives features from adjusted total-return history and existing factor scores
- predicts next `21` trading-day return

Trainer:

- runs local LightGBM only
- uses expanding walk-forward validation with an embargo between folds
- writes `model.txt`, `feature_manifest.json`, `metrics.json`, `metadata.json`, and `evaluation_report.json`

Predictor:

- loads the local artifact
- validates manifest compatibility
- returns predicted 21D and annualized scores plus top contributing drivers
- falls back to rules if the artifact is missing or invalid

Evaluation reporting:

- `apps/api/scripts/ml/evaluate_lightgbm_model.py` materializes a report under `apps/api/artifacts/reports/<model_version>/evaluation_report.json`
- the model-status endpoint now exposes `training_mode`, `artifact_classification`, and `validation_summary`

## Useful Commands

Frontend:

```bash
npm run dev
npm run lint
npm run build
```

Backend:

```bash
cd apps/api
.venv/bin/alembic upgrade head
.venv/bin/python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-12-31
.venv/bin/python scripts/import_corporate_actions.py --csv /absolute/path/to/corporate_actions.csv
.venv/bin/python scripts/ml/evaluate_lightgbm_model.py --artifact-dir artifacts/models/lightgbm_v1
```

Database checks:

```bash
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from instruments;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select count(*) from daily_bars;"
docker compose exec postgres psql -U postgres -d nse_portfolio -c "select min(trade_date), max(trade_date) from daily_bars;"
```

## Verified Local Checks

These were verified against the current code path:

- `npm run build`
- `GET /healthz`
- `GET /api/v1/models/current`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/benchmarks/summary`

## Current Limitations

- the checked-in raw history starts in 2024, so the first local LightGBM artifact is trained on a compressed walk-forward schedule unless you ingest older data
- some early backtest windows may still fall back to rules if the requested start date does not have enough trailing history for ML scoring
- benchmark summaries are still proxy portfolios, not official historical index reconstitutions
- tax logic is delivery-equity focused; derivatives are out of scope
- execution simulation is daily-bar based, not intraday or order-book based
- the backend is local-first and research-oriented; it is not a broker or execution platform

## Documentation

- [docs/architecture.md](docs/architecture.md)
- [docs/technical-plan.md](docs/technical-plan.md)
- [apps/api/README.md](apps/api/README.md)

## Disclaimer

This project is for research, education, and prototyping. It is not investment advice and not a substitute for a SEBI-registered advisor. Tax, fee, benchmark, and execution assumptions must be reviewed before any production or real-money use.
