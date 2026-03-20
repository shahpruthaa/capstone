# API Service

FastAPI backend scaffold for the NSE AI Portfolio Manager.

## Run locally without Docker

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

If you are using the repository `docker compose` stack, Postgres is exposed on host port `5433`.

## Run with Docker Compose

From the repository root:

```bash
docker compose up --build
```

API docs:
- `http://localhost:8000/docs`

## Migrations

```bash
cd apps/api
alembic upgrade head
```

If that fails because your host shell is picking up a broken global `alembic.exe`, install the API dependencies into the same Python first and then call the environment-local executable:

```bash
cd apps/api
python -m pip install -r requirements.txt
.venv\Scripts\alembic upgrade head
```

If your local Python has packaging issues on Windows, run the migration inside Docker instead:

```bash
docker compose exec api alembic upgrade head
```

## NSE Bhavcopy Ingestion

Example:

```bash
cd apps/api
python scripts/ingest_nse_bhavcopy.py --start-date 2025-01-01 --end-date 2025-01-10
```

Docker example:

```bash
docker compose exec api python scripts/ingest_nse_bhavcopy.py --start-date 2025-01-01 --end-date 2025-01-10
```

This pipeline:
- downloads NSE CM bhavcopy archives to `data/raw/nse/cm/...`
- parses supported legacy or UDiFF-style column names
- upserts `instruments`
- upserts `daily_bars`

Note:
- the archive URL format is based on the current NSE archive naming convention and may need adjustment if NSE changes its dissemination pattern again.
