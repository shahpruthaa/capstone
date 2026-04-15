# NSE AI Portfolio Manager Technical Plan

## Goal

Ship the branch rebuilt from `55b69df` as a stable capstone demo with:

- a local quant engine
- ensemble-aware runtime detection
- explicit degraded behavior
- Groq-assisted explanations
- one reproducible UI demo path

## Plan Status Summary

| Workstream                                       | Status   | Outcome                                                                                         |
| ------------------------------------------------ | -------- | ----------------------------------------------------------------------------------------------- |
| Baseline hardening and branch reset              | Complete | Branch behavior aligned to the `55b69df` capstone baseline                                      |
| Data and artifact pipeline standardization       | Complete | Canonical artifact layout and training order documented                                         |
| Backend runtime consolidation                    | Complete | `db_quant_engine.py` and runtime status now drive the system                                    |
| Frontend demo stabilization                      | Complete | Runtime banner, per-tab metadata, explicit fallback messaging                                   |
| Post-demo reliability fixes (tabs + Groq + perf) | Complete | Backtest route fix, unified API client usage, Groq chat/explain validation, chart binding fixes |
| UI warning-free simplification                   | Complete | Tab notices standardized to clean informational styling                                         |
| Runtime table font adjustments                   | Complete | Model runtime tables use monospace typography for better readability                            |
| Invested amount floor display                    | Complete | Total invested amounts now round down instead of nearest for conservative display               |
| Capstone docs and demo path                      | Complete | README, architecture, and technical plan match this branch                                      |
| Official benchmark reconstruction                | Partial  | Proxy-based local research strategies still in use                                              |
| Automated test depth                             | Partial  | Verification is strong, but coverage is not yet production-grade                                |

## 1. Baseline Hardening

Completed:

- restarted implementation from `55b69df6b0bf941abdef15e0f551b2175d7d93d2`
- kept the ensemble product as the target runtime
- separated explanation concerns from core quant concerns
- removed silent ambiguity around which model path is active

Result:

- the project now exposes one honest runtime state instead of implying full ensemble availability when artifacts are missing

## 2. Data and Artifact Pipeline

Completed:

- standardized the artifact layout under:
  - `artifacts/models/lightgbm_v1`
  - `artifacts/models/lstm_v1`
  - `artifacts/models/gnn_v1`
  - `artifacts/models/death_risk_v1`
  - `artifacts/models/ensemble_v1`
- added a canonical ensemble manifest materializer:
  - [materialize_ensemble_artifact.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/scripts/ml/materialize_ensemble_artifact.py)
- preserved the training dependency chain:
  1. LightGBM dataset
  2. LightGBM
  3. LSTM
  4. GNN
  5. death-risk
  6. ensemble manifest

Current expectation:

- the runtime reads artifacts from disk and reports component-level readiness
- missing artifacts no longer produce unclear behavior

## 3. Backend Runtime Consolidation

Completed:

- centralized runtime readiness in [model_runtime.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/model_runtime.py)
- made [db_quant_engine.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/db_quant_engine.py) the main orchestration layer for:
  - portfolio generation
  - holdings analysis
  - backtests
  - expected-return routing
  - fallback decisions
- upgraded [ensemble_scorer.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/ensemble_scorer.py) to:
  - work with aligned component payloads
  - compute degraded ensemble behavior explicitly
  - expose component scores and drivers
- moved Groq behind [groq_explainer.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/groq_explainer.py)

Runtime rule now:

- `LightGBM` is the core requirement for any ML-backed runtime
- if `LightGBM` is available and some non-core models are missing, the app uses `degraded_ensemble`
- if `LightGBM` is not available, the app uses `rules_only`

## 4. Public API Contract

Completed:

- `GET /api/v1/models/current` now exposes:
  - active mode
  - available and missing components
  - model version
  - artifact classification
  - training mode
  - Groq connectivity
  - fallback notes
- portfolio, analysis, and backtest responses now include:
  - `model_variant_applied`
  - `model_source`
  - `model_version`
  - `prediction_horizon_days`
  - `active_mode`
  - `artifact_classification`
- stock detail now includes:
  - final ensemble score
  - component scores
  - feature drivers
  - death-risk
  - optional explanation

## 5. Frontend Stabilization

Completed:

- top runtime banner now shows:
  - market data readiness
  - runtime mode
  - training mode
  - artifact classification
  - Groq availability
  - available components
- `Generate` now shows runtime metadata and model-driver context
- `Analyze` now surfaces model source, mode, version, and ML score counts
- `Backtest` now shows ensemble runtime details instead of vague hybrid wording
- `AIChat` now uses the correct portfolio shape and passes clean context

Important outcome:

- the UI no longer hides degraded or fallback states

Additional completion items:

- fixed Compare chart rendering issue where custom bar coloring used invalid `rect` children instead of `Cell`
- aligned dashed-line binding with backend strategy key (`Nifty 50 Proxy`)
- removed direct relative `/api/...` calls from AI components and routed them through `backendApi.ts`

## 5.1 Backtest/Analyze/Compare Reliability Fixes

Completed:

- corrected a backtest backend bug in `run_backtest` where selection date propagation used the wrong variable (`as_of_date` instead of `selection_date`)
- validated `/api/v1/analysis/portfolio`, `/api/v1/backtests/run`, and `/api/v1/benchmarks/summary` against live local runtime

Result:

- Analyze and Compare tabs are backend-aligned
- Backtest route no longer fails with internal server error for valid payloads

## 5.2 Load-Time Optimization

Completed:

- converted runtime-only type imports in `backendApi.ts` to `import type` to reduce unnecessary frontend bundle work
- added API request timeout control in the frontend adapter
- added short-lived caching for model-status and market-summary calls used across multiple tabs

Result:

- faster perceived load and tab transitions, especially when backend endpoints are slow or temporarily unavailable

## 5.3 Groq LLM Enablement

Completed:

- configured backend env contract (`APP_GROQ_API_KEY`, optional `APP_GROQ_MODEL`) in `apps/api/.env` and `apps/api/.env.example`
- validated live Groq chat response via `POST /api/v1/explain/chat`

Result:

- Groq-backed chat and portfolio explanation routes are operational when key is configured

## 5.4 Directory Cleanup

Completed:

- migrated dataset artifacts to canonical `apps/api/artifacts/datasets/lightgbm_v1`
- removed stale nested folder `apps/api/apps/api/artifacts`

Result:

- single canonical artifact tree and cleaner operational conventions

## 5.5 UI Simplification (No Warning-Themed Banners)

Completed:

- replaced warning-tone tab notices with neutral informational notices in Generate, Analyze, Backtest, Compare, and top runtime banner contexts
- retained all runtime and fallback details as text so behavior remains explicit without noisy alert framing

Result:

- cleaner visual presentation while preserving operational transparency

## 5.6 Further Improvements Backlog

Recommended next steps:

- add benchmark-result caching and warm-up to reduce first-load compare latency
- expose endpoint-specific frontend timeout settings through environment variables
- include full click-path Playwright smoke test in CI
- add structured error-code mapping between backend and UI notices
- automate benchmark constituent reconstruction from licensed data sources

## 6. Capstone Demo Path

Recommended presentation flow:

1. `docker compose up -d --build`
2. `docker compose exec api alembic upgrade head`
3. ingest bhavcopy data
4. import corporate actions
5. train or copy artifacts into the canonical directories
6. run `GET /api/v1/models/current`
7. open the UI
8. generate a portfolio
9. analyze a holdings basket
10. run a backtest
11. compare benchmarks
12. show stock detail and AI explanations if Groq is configured

## 7. Verification

Completed locally during this stabilization pass:

- backend Python compile check
- frontend lint
- frontend production build

Verification commands:

```powershell
python -m compileall apps/api/app apps/api/scripts
npm run lint
npm run build
```

## 8. Remaining Partial Areas

These are intentionally called out so the capstone is honest:

- official benchmark constituent reconstruction
- deeper automated testing
- live intraday execution behavior
- artifact quality itself, which still depends on locally training or supplying the models

## 9. Acceptance Criteria Mapping

| Acceptance target                               | Status                                        | Notes                                     |
| ----------------------------------------------- | --------------------------------------------- | ----------------------------------------- |
| Stack starts locally                            | Complete                                      | Dockerized services and docs are in place |
| Artifacts are discovered and reported correctly | Complete                                      | Runtime status is component-aware         |
| Full demo can run from the UI                   | Complete, subject to local data and artifacts | UI and backend paths are wired            |
| Degraded-state demo is transparent              | Complete                                      | Banner and route metadata expose it       |
| README matches runtime behavior                 | Complete                                      | Updated for this branch                   |
