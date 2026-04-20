# NSE Atlas

Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.

![Product](https://img.shields.io/badge/Product-NSE%20Atlas-0b7285)
![Repository Slug](https://img.shields.io/badge/Repository%20Slug-nse--ai--portfolio--manager-495057)
![Frontend Package](https://img.shields.io/badge/Frontend%20Package-nse--ai--portfolio--manager-343a40)
![API Display Name](https://img.shields.io/badge/API%20Display%20Name-NSE%20Atlas%20API-2b8a3e)

## Naming Conventions

Use these identifiers consistently in release notes, badges, and docs:

| Scope                 | Canonical Value                                                                            | Usage                                         |
| --------------------- | ------------------------------------------------------------------------------------------ | --------------------------------------------- |
| Product display name  | NSE Atlas                                                                                  | UI labels, headings, release titles           |
| Product subtitle      | Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets. | Hero text, product summary                    |
| Repository slug       | nse-ai-portfolio-manager                                                                   | Git remote/repo path, CI references           |
| Frontend package name | nse-ai-portfolio-manager                                                                   | `package.json` name and lockfile root package |
| API display name      | NSE Atlas API                                                                              | FastAPI title and environment app name        |

## Release Checklist

- [ ] Product display name is `NSE Atlas` across README headings, release notes, and app UI labels.
- [ ] Product subtitle is exactly `Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.` in release-facing docs.
- [ ] Repository slug remains `nse-ai-portfolio-manager` in repository path references and CI workflow/config docs.
- [ ] Frontend package name remains `nse-ai-portfolio-manager` in `package.json` and `package-lock.json` root package metadata.
- [ ] API display name is `NSE Atlas API` in `apps/api/app/core/config.py`, `apps/api/.env.example`, and `docker-compose.yml`.
- [ ] README badges and the Naming Conventions table are updated if any canonical value changes.

Current snapshot: the checked-out merge commit `6f36924ad85bbca4fa2cf6284a71a5404f832482`, which combines the documentation refactor baseline with the LIGHTGBM_HYBRID generate-path ML injection update in `db_quant_engine.py`.

This repository is organized as a React + Vite frontend, a FastAPI backend, local model artifacts, and a small amount of supporting data, infra, and smoke-test tooling.

## What Exists In This Directory

```text
.
├── README.md
├── docker-compose.yml
├── index.html
├── package.json
├── package-lock.json
├── tsconfig.json
├── vite.config.ts
├── src/
├── apps/
│   └── api/
├── data/
├── docs/
├── infra/
├── scripts/
└── tmp/
```

The main working areas are:

- `src/`: the browser app, tab layout, shared services, and styling.
- `apps/api/`: the FastAPI service, ingestion utilities, model runtime code, and local artifacts.
- `docs/`: architecture, technical plan, and proof notes for the current snapshot.
- `infra/docker/`: Dockerfiles used by `docker compose`.
- `scripts/`: maintenance and smoke-test utilities.
- `tmp/ui-smoke/`: screenshots and ad hoc smoke-test artifacts created during validation runs.

## Product Surface

The current frontend shell in `src/App.tsx` exposes five main product tabs plus the persistent chat widget:

- `Market`
- `Portfolio`
- `Trade Ideas`
- `Backtest`
- `Compare`
- `AI Chat`

The `Portfolio` tab is a workspace with two modes:

- Build Portfolio
- Analyze Holdings

The app now presents a stable sidebar/topbar shell, runtime badges, and a live “live picks” count when a portfolio has been generated.

## Core Frontend Files

```text
src/
├── App.tsx
├── index.css
├── main.tsx
├── components/
│   ├── AIChat.tsx
│   ├── AnalyzeTab.tsx
│   ├── BacktestTab.tsx
│   ├── CompareTab.tsx
│   ├── GenerateTab.tsx
│   ├── MarketTab.tsx
│   ├── PortfolioWorkspace.tsx
│   ├── TradeIdeasTab.tsx
│   └── MetricCard.tsx
├── data/
│   └── stocks.ts
└── services/
    ├── backendApi.ts
    ├── backtestEngine.ts
    ├── benchmarkService.ts
    ├── localAdvisor.ts
    └── portfolioService.ts
```

### Frontend responsibilities

- `GenerateTab.tsx` builds a portfolio from capital, risk attitude, and sector constraints.
- `AnalyzeTab.tsx` lets the user paste or assemble holdings and produces risk/diversification analysis.
- `BacktestTab.tsx` runs historical replay with model-variant selection and trading-friction controls.
- `CompareTab.tsx` shows benchmark comparison and projected-growth charts.
- `AIChat.tsx` is a floating assistant that sends portfolio-aware prompts to the backend explanation API.
- `backendApi.ts` is the single request/response adapter between UI types and backend DTOs.

## Backend Surface

```text
apps/api/
├── README.md
├── alembic.ini
├── alembic/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── routes/
│   ├── core/
│   ├── db/
│   ├── ingestion/
│   ├── ml/
│   ├── models/
│   ├── schemas/
│   └── services/
├── artifacts/
└── scripts/
```

### Backend responsibilities

- `app/main.py` boots the API, applies CORS, preloads local bootstrap state, and records model-runtime readiness.
- `app/api/router.py` wires together the route modules for portfolio, analysis, backtests, benchmarks, market data, models, news, explanations, stock detail, and trade ideas.
- `app/services/db_quant_engine.py` remains the main orchestration layer for portfolio generation, analysis, and backtesting, and now injects LIGHTGBM predictions into selected securities during `LIGHTGBM_HYBRID` generation when artifacts are available.
- `app/services/model_runtime.py` reports what is available on disk and whether the runtime is `full_ensemble`, `degraded_ensemble`, or `rules_only`.
- `app/services/ensemble_scorer.py` combines component predictions and emits runtime-aware metadata.
- `app/services/groq_explainer.py` owns the explanation/chat boundary.
- `app/services/news_intelligence.py` and `app/api/routes/news.py` support market-context narration.

## API Endpoints In Use

| Method | Endpoint                      | Purpose                                 |
| ------ | ----------------------------- | --------------------------------------- |
| `GET`  | `/api/v1/models/current`      | Runtime readiness and component status  |
| `GET`  | `/api/v1/market-data/summary` | Available local market data window      |
| `POST` | `/api/v1/portfolio/generate`  | Generate a portfolio                    |
| `POST` | `/api/v1/analysis/portfolio`  | Analyze holdings                        |
| `POST` | `/api/v1/backtests/run`       | Run a backtest                          |
| `GET`  | `/api/v1/benchmarks/summary`  | Benchmark comparison summary            |
| `GET`  | `/api/v1/trade-ideas`         | Trade-idea shortlist                    |
| `POST` | `/api/v1/explain/portfolio`   | Portfolio explanation                   |
| `POST` | `/api/v1/explain/chat`        | AI chat assistant                       |
| `GET`  | `/api/v1/stock/...`           | Stock detail / stock narrative surfaces |

## Runtime Behavior

The current codebase is explicitly local-first:

- The API reads local artifacts from `apps/api/artifacts/models/*`.
- The backend reports runtime status before the UI asks for model-backed behavior.
- In `LIGHTGBM_HYBRID` generation, selected names can be stamped with ML fields (`expected_return_source`, prediction horizon, model version) before scoring.
- If the model path is unavailable, the system falls back to rule-based behavior rather than failing silently.
- Groq is used only for explanation/chat surfaces and is not required for the quant path.
- CORS is configured for local browser origins used by the dev and smoke workflows, including ports `3000`, `3001`, `4173`, and `5173` on `localhost` and `127.0.0.1`.

## Local Setup

### Frontend

```bash
npm install
npm run dev
```

Default dev server: `http://localhost:3000`

### Backend

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

API docs: `http://localhost:8000/docs`

### Docker

```bash
docker compose up -d api postgres redis
```

The compose stack is the easiest way to keep the frontend and backend aligned with the current snapshot.

## Smoke Validation

This directory includes a smoke runner at `scripts/ui-smoke-playwright.mjs` and a current ad hoc runner in `tmp/ui-smoke/quick-smoke-current.mjs`.

Current validated flows:

- Generate
- Analyze
- Backtest
- Compare
- AI Chat

## Notes

- `Market` and `Trade Ideas` are first-class tabs in the shell even when individual panels are still presentation-heavy.
- `CompareTab` uses backend benchmark summaries and local proxy metadata.
- `GenerateTab` and `BacktestTab` both expose runtime status, artifact classification, and model-version context.
- `apps/api/README.md` contains the backend-specific setup and data pipeline notes.
