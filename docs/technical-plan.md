# NSE AI Portfolio Manager Technical Plan

## Goal

Keep the current `6f36924ad85bbca4fa2cf6284a71a5404f832482` snapshot stable as a local capstone demo with:

- a local quant engine
- runtime-aware model reporting
- explicit fallback modes
- explanation/chat as an optional dependency
- repeatable UI validation

## Plan Status Summary

| Workstream                        | Status   | Outcome                                                                                     |
| --------------------------------- | -------- | ------------------------------------------------------------------------------------------- |
| Runtime and CORS stabilization    | Complete | Browser requests from local dev ports succeed consistently                                  |
| Backend runtime consolidation     | Complete | `db_quant_engine.py`, `ensemble_scorer.py`, and `model_runtime.py` define the core behavior |
| LIGHTGBM hybrid injection path    | Complete | `generate_portfolio` stamps selected names with ML return source/horizon/version metadata   |
| Frontend shell and tab structure  | Complete | `Market`, `Portfolio`, `Trade Ideas`, `Backtest`, `Compare`, and `AI Chat` are wired        |
| Explanation boundary cleanup      | Complete | Groq remains a non-blocking helper for chat/explanations only                               |
| UI smoke validation               | Complete | Generate, Analyze, Backtest, Compare, and AI Chat pass in the current snapshot              |
| Official benchmark reconstruction | Partial  | Proxy-based benchmark output is still used for local demo continuity                        |
| Regression automation depth       | Partial  | Smoke coverage exists, but broader test automation still needs expansion                    |

## 1. Current Branch Snapshot

This plan applies to the checked-out merge state in this directory, not the earlier 55b69df-only baseline.

Current characteristics:

- frontend shell is fully tabbed and runtime-aware
- backend startup includes local bootstrap and model-status inspection
- CORS is tuned for local UI ports used by dev and smoke workflows
- current docs match the live file layout and current routes

## 2. Backend Runtime Model

Completed:

- `app/main.py` bootstraps local state and loads model runtime metadata at startup
- `model_runtime.py` exposes component readiness, artifact classification, and runtime mode
- `db_quant_engine.py` remains the orchestration layer for generation, analysis, and backtests
- `db_quant_engine.py` now injects LightGBM ensemble predictions into selected securities for `LIGHTGBM_HYBRID` generation when artifacts are available, then scores with that model-source metadata
- `ensemble_scorer.py` combines LightGBM, LSTM, GNN, and death-risk signals when available
- `groq_explainer.py` is isolated behind explanation routes so quant behavior is not coupled to LLM availability

Runtime rule in force:

- `full_ensemble` when the required artifacts are present and the optional set is healthy
- `degraded_ensemble` when the core ML path exists but not every optional component is available
- `rules_only` when the ML artifact path is unavailable

## 3. Frontend Product Flow

Completed:

- `Market` is a first-class entry point in the shell
- `Portfolio` is split into build and analysis views
- `Trade Ideas` exists as a dedicated tab in the nav
- `Backtest` includes runtime context, tax, and cost framing
- `Compare` renders benchmark and growth views from backend summaries
- `AIChat` uses the current portfolio context and shared backend adapter

The current product flow is:

1. open the app and inspect runtime badges
2. generate a portfolio
3. inspect model runtime and allocations
4. analyze holdings
5. run a backtest
6. compare strategies
7. ask the assistant for narrative context

## 4. API and Data Plan

Completed:

- endpoint coverage now includes the current model status, market-data summary, portfolio generation, analysis, backtest, benchmark summary, trade ideas, stock detail, and explanation routes
- the frontend consumes a single typed adapter layer in `src/services/backendApi.ts`
- local market data, corporate actions, and artifact files remain the source of truth for offline/demo behavior

Data and artifact locations that matter in the current tree:

- `data/raw/` for NSE source archives
- `apps/api/artifacts/models/lightgbm_v1/`
- `apps/api/artifacts/models/lstm_v1/`
- `apps/api/artifacts/models/gnn_v1/`
- `apps/api/artifacts/models/death_risk_v1/`
- `apps/api/artifacts/models/ensemble_v1/`

## 5. Validation Plan

Completed in the current snapshot:

- backend import/startup verification
- backend health and CORS preflight checks
- frontend production build validation
- one-pass UI smoke validation for all major screens

The smoke runner is currently represented in the repository by:

- `scripts/ui-smoke-playwright.mjs`
- `tmp/ui-smoke/quick-smoke-current.mjs`

## 6. Remaining Work

Still partial:

- official benchmark reconstruction from a fully authoritative constituent history
- broader regression automation beyond the smoke pass
- artifact quality improvements from fresh training runs
- execution-grade integrations outside the research/local-demo scope

## 7. Acceptance Criteria Mapping

| Acceptance target                                        | Status   | Notes                                                                 |
| -------------------------------------------------------- | -------- | --------------------------------------------------------------------- |
| Local stack starts                                       | Complete | Dockerized backend and frontend are aligned with the current snapshot |
| Runtime readiness is visible                             | Complete | `/api/v1/models/current` drives the UI banner and fallback display    |
| Browser fetches work from local dev ports                | Complete | CORS is enabled for local UI origins used in this directory           |
| Generate/Analyze/Backtest/Compare/AI Chat are functional | Complete | Verified by current smoke pass                                        |
| Documentation matches the current tree                   | Complete | README, architecture, technical plan, and proof notes are aligned     |
