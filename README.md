# NSE AI Portfolio Manager

This branch is the capstone baseline rebuilt from commit `55b69df6b0bf941abdef15e0f551b2175d7d93d2` on `origin/kairavee-platform`.

It is a local-first, full-stack NSE portfolio research application with:

- a React + Vite frontend
- a FastAPI backend
- PostgreSQL + TimescaleDB for market data and run history
- local ML artifact loading for `LightGBM`, `LSTM`, `GNN`, and `death-risk`
- a strict ensemble runtime contract with explicit degraded and rules-only modes
- Groq-backed explanation routes that never block the core quant workflow

This repo does not depend on QuantEngine or any external quant API.

## What The Project Does

The app supports one end-to-end capstone flow:

1. ingest NSE bhavcopy and instrument data
2. import corporate actions
3. build or load local ML artifacts
4. verify runtime readiness from `GET /api/v1/models/current`
5. generate a portfolio
6. analyze existing holdings
7. run a realistic backtest with taxes, fees, and rebalance logic
8. compare against benchmark strategies
9. optionally ask Groq for natural-language explanations of stocks, portfolios, and chat prompts

## Runtime Modes

The backend always reports its real runtime state. It does not silently mix hidden fallbacks.

| Mode | When it is used | Quant behavior | Explanation behavior |
| --- | --- | --- | --- |
| `full_ensemble` | `LightGBM`, `LSTM`, `GNN`, and `death-risk` artifacts are all valid | Equities use the full ensemble scorer, ETFs stay on rules | Groq explanation works if configured |
| `degraded_ensemble` | `LightGBM` is valid but one or more non-core ensemble components are missing | Equities use the available ensemble subset with normalized weights | Groq explanation works if configured |
| `rules_only` | `LightGBM` is missing or invalid | Portfolio generation, analysis, and backtests continue with rules | Groq explanation may still work if configured |

## System Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Frontend | React, Vite, TypeScript | Generate, Analyze, Backtest, Compare, AI chat UI |
| API | FastAPI | Portfolio, analysis, backtests, model status, stock detail, explain, news |
| Quant runtime | Python services | Universe selection, factor scoring, ensemble orchestration, allocation, replay |
| Data store | PostgreSQL + TimescaleDB | Instruments, daily bars, corporate actions, portfolio runs, backtests |
| Cache/queue | Redis | Optional local support service |
| ML artifacts | Local filesystem | `lightgbm_v1`, `lstm_v1`, `gnn_v1`, `death_risk_v1`, `ensemble_v1` |
| LLM | Groq | Natural-language explanation only |

More detail: [docs/architecture.md](C:/Users/pruth/nse-ai-portfolio-manager/docs/architecture.md)

## Repo Structure

```text
apps/api/
  app/
    api/routes/           FastAPI route handlers
    ml/                   LightGBM, LSTM, GNN, death-risk, ensemble code
    services/             Quant engine, runtime status, Groq explainer, news
    models/               SQLAlchemy models
  alembic/                DB migrations
  scripts/
    ingest_nse_bhavcopy.py
    import_corporate_actions.py
    ml/
      build_ml_dataset.py
      train_lightgbm_model.py
      train_lstm_model.py
      train_gnn_model.py
      train_death_risk_model.py
      evaluate_lightgbm_model.py
      materialize_ensemble_artifact.py
src/
  components/             Generate, Analyze, Backtest, Compare, AI chat
  services/               Backend API adapters and UI domain types
docs/
  architecture.md
  technical-plan.md
```

## API Surface

Core routes:

- `GET /healthz`
- `GET /api/v1/models/current`
- `GET /api/v1/market-data/summary`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

Capstone demo routes:

- `GET /api/v1/stock/{symbol}`
- `GET /api/v1/news/market-context`
- `POST /api/v1/explain/stock`
- `POST /api/v1/explain/portfolio`
- `POST /api/v1/explain/chat`

## Local Setup

### 1. Start the stack

```powershell
docker compose up -d --build
```

Frontend: [http://localhost:3000](http://localhost:3000)

Backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run database migrations

```powershell
docker compose exec api alembic upgrade head
```

### 3. Ingest market data

```powershell
docker compose exec api python scripts/ingest_nse_bhavcopy.py --start-date 2024-01-01 --end-date 2025-03-15
```

Optional corporate actions import:

```powershell
docker compose exec api python scripts/import_corporate_actions.py --csv /app/data/corporate_actions.csv
```

### 4. Build or load artifacts

The canonical artifact layout is:

```text
artifacts/models/lightgbm_v1/
artifacts/models/lstm_v1/
artifacts/models/gnn_v1/
artifacts/models/death_risk_v1/
artifacts/models/ensemble_v1/
```

Expected contents by model directory:

- weights
- feature manifest
- training metadata
- evaluation summary
- training end date
- artifact classification such as `bootstrap` or `standard`

Example training flow:

```powershell
docker compose exec api python scripts/ml/build_ml_dataset.py
docker compose exec api python scripts/ml/train_lightgbm_model.py
docker compose exec api python scripts/ml/train_lstm_model.py
docker compose exec api python scripts/ml/train_gnn_model.py
docker compose exec api python scripts/ml/train_death_risk_model.py
docker compose exec api python scripts/ml/materialize_ensemble_artifact.py
```

### 5. Verify runtime readiness

Open [http://localhost:8000/docs](http://localhost:8000/docs) or call `GET /api/v1/models/current`.

That endpoint reports:

- active runtime mode
- model source
- available components
- missing components
- model versions
- artifact classification
- training mode
- Groq connectivity
- fallback reason and notes

## Frontend Demo Flow

This is the supported local capstone demo path:

1. start Docker
2. confirm [http://localhost:3000](http://localhost:3000) loads
3. check the runtime banner at the top of the UI
4. generate a portfolio in `Generate`
5. inspect stock drivers and runtime metadata
6. analyze an existing holdings basket in `Analyze`
7. run a backtest in `Backtest`
8. compare against local benchmark strategies in `Compare`
9. use the AI chat or stock explanation panels if Groq is configured

## What Is Deterministic Locally vs Dependent On Groq

Locally deterministic:

- data ingestion
- factor computation
- ensemble/runtime readiness detection
- portfolio construction
- rebalance recommendations
- backtests
- taxes and fees
- benchmark summary generation
- stock detail quantitative payloads

Groq-dependent:

- natural-language stock explanations
- natural-language portfolio explanations
- AI chat answers
- some market-context narrative enrichment

Important: the quant engine remains usable without Groq. Explanation routes degrade gracefully and the runtime banner reports Groq availability.

## Implementation Status

| Workstream | Status | Notes |
| --- | --- | --- |
| Local React + FastAPI integration | Complete | Frontend uses backend routes directly |
| Dockerized local stack | Complete | `web`, `api`, `postgres`, `redis` |
| DB schema and migrations | Complete | Includes Timescale and corporate-action support |
| NSE bhavcopy ingestion | Complete | Raw archive caching, instrument upsert, progress bar |
| Corporate-action import path | Complete | Schema, import script, adjustment service |
| Rule-based quant engine | Complete | Allocation, analysis, replay, taxes, fees |
| Ensemble runtime contract | Complete | Full, degraded, and rules-only modes are explicit |
| Model status surface | Complete | Component-level readiness, Groq, notes |
| Stock detail and explanation boundary | Complete | Quant payload and Groq explanation separated |
| Frontend runtime notices | Complete | Banner plus per-tab runtime metadata |
| Benchmark comparison | Partial | Proxy-based local research benchmarks, not official constituent reconstruction |
| Artifact training outputs | Partial | Training scripts exist; readiness depends on local artifacts actually being produced |
| Automated tests | Partial | Manual verification path is stronger than test coverage right now |

## Development Phases

| Phase | Status | Outcome |
| --- | --- | --- |
| Phase 1: Frontend prototype | Complete | Generate, Analyze, Backtest, Compare UX exists |
| Phase 2: Local backend and DB | Complete | FastAPI, Postgres, Timescale, Redis, Docker |
| Phase 3: NSE data pipeline | Complete | Bhavcopy ingestion and market-data readiness endpoint |
| Phase 4: Portfolio engine and simulator | Complete | Rule allocator, backtest, fees, taxes, rebalance |
| Phase 5: ML alpha models | Complete | Local LightGBM, LSTM, GNN, death-risk code and loaders |
| Phase 6: Ensemble runtime and status | Complete | Component-aware runtime detection and degraded behavior |
| Phase 7: Explainability and capstone packaging | Complete | Groq boundary, stock detail, runtime UI, branch-specific docs |
| Phase 8: Official benchmark reconstitution | Partial | Still proxy-based |
| Phase 9: Production hardening and full automated testing | Partial | Good local demo path, lighter automated coverage than production systems |

## Known Limitations

- Official index constituent reconstitution is not complete; benchmark strategies are proxy-based.
- Ensemble quality depends on locally trained artifacts being present and valid.
- Groq is required for the full explanation story, but not for the quant engine.
- Live market behavior is still EOD research-grade, not intraday execution-grade.
- Fee and tax logic are detailed for listed delivery-equity research, but still need maintenance as regulations change.

## Related Docs

- [Architecture](C:/Users/pruth/nse-ai-portfolio-manager/docs/architecture.md)
- [Technical Plan](C:/Users/pruth/nse-ai-portfolio-manager/docs/technical-plan.md)
