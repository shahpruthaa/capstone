# NSE AI Portfolio Manager Technical Plan

## 1. Goal

Ship a fully local NSE portfolio research application where:

- the UI uses only the local FastAPI backend
- the backend uses the local database and local model artifacts
- LightGBM hybrid expected returns are the default runtime path when a valid artifact exists
- rules remain the safe fallback when the artifact is missing or invalid

## 2. Current Implementation Baseline

Already implemented:

- local FastAPI routes for portfolio generation, holdings analysis, backtests, benchmark summaries, and model status
- PostgreSQL + TimescaleDB schema and migrations
- NSE bhavcopy ingestion with raw archive caching
- corporate-action adjustment and dividend handling
- constrained allocator over shrinkage covariance
- holdings analyzer and rebalance action generation
- historical replay with stop-loss, take-profit, fees, taxes, and cooldown-based re-entry rules
- local LightGBM dataset builder, trainer, predictor, and artifact loader
- UI support for model variant, model version, training mode, artifact classification, and top ML drivers
- backend market-data summary endpoint for readiness and valid-range derivation
- benchmark provenance metadata in the compare flow
- evaluation report generation under `artifacts/reports`
- UI adapters wired directly to backend endpoints with no silent local portfolio/backtest/benchmark fallbacks

Still pending or partial:

- official benchmark constituent ingestion
- deeper pre-2024 history for longer walk-forward training
- automated test coverage
- richer factor set beyond price/liquidity-derived inputs
- broker profile abstraction and more detailed fee schedules
- standard-history v2 artifact with positive held-out validation metrics

## 3. Local LightGBM Plan

### Runtime policy

- request default: `LIGHTGBM_HYBRID`
- equity expected returns: local LightGBM + rule blend
- ETF expected returns: rules only
- missing or invalid artifact: automatic runtime fallback to `RULES`

### Dataset design

- one row per `(symbol, decision_date)`
- monthly decision dates only
- trailing `252` trading-day feature window
- next `21` trading-day return target
- adjusted total-return history
- numeric features winsorized and z-scored cross-sectionally per decision date
- sector and market-cap bucket encoded categorically

### Training design

- local LightGBM regressor
- expanding walk-forward validation
- embargo between train, validation, and test folds
- primary metric: out-of-sample mean Spearman rank IC
- secondary metric: top-minus-bottom forward return spread

### Practical repo constraint

- the checked-in cache begins in 2024, so the trainer now supports compressed walk-forward windows when the preferred `24/6/6` monthly split is impossible
- the current bootstrap artifact can be accepted with negative IC metadata when history is too thin to satisfy the original rejection gate
- once older history is ingested, retrain with the longer preferred walk-forward schedule
- the UI now labels that state explicitly through `training_mode` and `artifact_classification`

## 4. UI Integration Plan

### Generate

- submit directly to `POST /api/v1/portfolio/generate`
- preflight model availability via `GET /api/v1/models/current`
- surface `model_variant`, `model_source`, `model_version`, and `prediction_horizon_days`
- surface training mode and bootstrap-vs-standard artifact status
- show top ML drivers on selected equities
- remove silent heuristic fallback behavior

### Analyze

- submit directly to `POST /api/v1/analysis/portfolio`
- show `model_variant_applied`
- show ML scores by holding when present
- use backend rebalance actions as the authoritative response

### Backtest

- submit directly to `POST /api/v1/backtests/run`
- preflight model availability via `GET /api/v1/models/current`
- derive valid default dates from `GET /api/v1/market-data/summary`
- show model runtime info beside the result
- keep `RULES` vs `LIGHTGBM_HYBRID` selector in the UI
- remove silent local simulation fallback behavior

### Compare

- submit directly to `GET /api/v1/benchmarks/summary`
- show backend benchmark notes and per-strategy provenance metadata
- label proxy benchmarks clearly in the UI
- if the endpoint fails, show the failure instead of silently substituting a different benchmark engine

### Environment wiring

- frontend API host comes from `VITE_API_BASE_URL`
- default local value remains `http://localhost:8000`
- `.env.example` documents the expected frontend API target

## 5. API and Contract Plan

Active routes:

- `GET /healthz`
- `GET /api/v1/models/current`
- `POST /api/v1/portfolio/generate`
- `POST /api/v1/analysis/portfolio`
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/benchmarks/summary`
- `GET /api/v1/market-data/summary`
- `POST /api/v1/market-data/ingestions/nse-bhavcopy`

Contract requirements:

- generation and backtest responses must always return model source metadata
- analysis responses must return the applied model variant and any ML scores
- model status must reflect whether the artifact is truly loadable, not just whether files exist
- model status should include `training_mode`, `artifact_classification`, and `validation_summary`
- benchmark summaries should include construction/proxy metadata per strategy
- market-data summary is the authoritative source for valid local backtest dates

## 6. Data Pipeline Plan

### Market data

- use cached NSE bhavcopy ZIP files as the current local EOD source
- ingest into `instruments` and `daily_bars`
- enrich selected symbols with sector, instrument type, and market-cap bucket

### Corporate actions

- keep schema and import flow
- apply split/bonus factors to OHLC and close histories
- add dividend cash credits into total-return series and backtests

### Benchmarks

- current state: proxy benchmarks only
- current endpoint now labels proxy construction explicitly
- next step: add official index constituent files and benchmark series storage

## 7. Simulation Engine Plan

Keep the current event-driven daily replay model, but harden these areas:

- maintain dated fee and tax schedules
- keep the true `12-month` listed-equity LTCG classification aligned with new tax schedules
- externalize brokerage profiles instead of treating one discount-broker plan as universal
- keep stop-loss / take-profit fills gap-aware and based on adjusted OHLC bars
- preserve identical fee/tax/rebalance logic between `RULES` and `LIGHTGBM_HYBRID`; only the expected-return source should differ

## 8. Verification Plan

Minimum verification after each major change:

- `npm run build`
- API import/startup check
- `/healthz`
- `/api/v1/models/current`
- `/api/v1/market-data/summary`
- end-to-end smoke calls for:
  - portfolio generation
  - holdings analysis
  - backtest
  - benchmark summary
- confirm the UI tabs map to those exact backend routes through `src/services/backendApi.ts`

ML-specific verification:

- dataset shape and leakage checks
- artifact loader validation
- inference fallback when artifact is missing
- side-by-side `RULES` vs `LIGHTGBM_HYBRID` backtest comparison

## 9. Near-Term Execution Order

1. Remove stale scaffold and frontend fallback messaging.
2. Make LightGBM hybrid the default request path and validate artifact loading.
3. Ingest enough local bhavcopy history to support the DB-backed endpoints.
4. Build the ML dataset and train the first local artifact.
5. Generate the evaluation report under `artifacts/reports`.
6. Run endpoint smoke checks against the local stack.
7. Replace proxy benchmarks with official reconstitution as the next research milestone.
