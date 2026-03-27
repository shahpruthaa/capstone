# API Service

Local FastAPI backend for the NSE AI Portfolio Manager.

This service is the active portfolio engine used by the UI. It serves:

- portfolio generation
- holdings analysis
- historical backtests
- benchmark summaries
- model status
- market-data ingestion

## Setup

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Database Services

From the repository root:

```bash
docker compose up -d postgres redis
```

Host ports:

- Postgres: `5433`
- Redis: `6379`

## Migrations

```bash
cd apps/api
.venv/bin/alembic upgrade head
```

## Ingest Cached NSE History

```bash
cd apps/api
.venv/bin/python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-12-31
```

## Train the Local LightGBM Artifact

```bash
cd apps/api
.venv/bin/python scripts/ml/build_ml_dataset.py --start-date 2024-12-01 --end-date 2025-12-31 --max-symbols 120
.venv/bin/python scripts/ml/train_lightgbm_model.py \
  --dataset-csv artifacts/datasets/lightgbm_v1/ml_dataset.csv \
  --dataset-manifest-json artifacts/datasets/lightgbm_v1/dataset_manifest.json \
  --artifact-dir artifacts/models/lightgbm_v1
```

## Run the API

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Docs:

- [http://localhost:8000/docs](http://localhost:8000/docs)

## Current Routes

- `GET /`
- `GET /healthz`
- `GET /api/v1/models/current`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

## Notes

- runtime is local-first; there is no external quant API dependency in the active request path
- `LIGHTGBM_HYBRID` is the default request mode for generation and backtests
- if the model artifact is missing or invalid, the backend automatically falls back to the rule model
