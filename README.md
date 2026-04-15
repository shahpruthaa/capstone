# NSE AI Portfolio Manager

Frontend + local API capstone system for NSE portfolio generation, holdings analysis, backtesting, benchmark comparison, and AI-assisted explanations.

This README reflects what is implemented in the current codebase.

## What Has Been Built So Far

### 1) App shell and navigation

The React app (`src/App.tsx`) now has a fixed sidebar + topbar layout with five tabs:

- `Market`
- `Portfolio` (portfolio generation flow)
- `Trade Ideas` (currently backed by holdings analysis UI)
- `Backtest`
- `Compare`

The sidebar also shows status placeholders for:

- NSE market status
- model/ensemble status
- latest data date

### 2) Portfolio generation tab (`GenerateTab`)

Implemented:

- Investment amount input
- Three risk profiles: `NO_RISK`, `LOW_RISK`, `HIGH_RISK`
- Runtime model status fetch (`GET /api/v1/models/current`)
- Portfolio generation call (`POST /api/v1/portfolio/generate`)
- Response mapping to frontend portfolio model
- Portfolio metrics cards (beta, sharpe proxy, expected return/vol)
- Allocation visualizations (pie + sector bar chart via Recharts)
- Allocation table with model drivers
- Transaction-cost breakdown using Indian fee assumptions
- AI explanation trigger (`POST /api/v1/explain/portfolio`)

### 3) Holdings analysis / trade-ideas tab (`AnalyzeTab`)

Implemented:

- Add/remove holdings workflow
- NSE symbol search over local universe (`src/data/stocks.ts`)
- Portfolio analysis call (`POST /api/v1/analysis/portfolio`)
- Risk/diversification and warning metrics
- Sector exposure chart
- Factor exposure bars (when returned)
- ML scores by holding (when returned)
- Sector correlation matrix (based on local sector-correlation map)
- Rebalancing actions panel
- Local advisory text generation (`generateRebalancingAdvice`)

### 4) Backtest tab (`BacktestTab`)

Implemented:

- Date window, stop-loss, take-profit, rebalance frequency controls
- Model variant selection (`RULES` or `LIGHTGBM_HYBRID`)
- Runtime model/data context fetch:
  - `GET /api/v1/models/current`
  - `GET /api/v1/market-data/summary`
- Backtest execution (`POST /api/v1/backtests/run`)
- Full metrics dashboard (return, CAGR, sharpe/sortino/calmar, drawdown, win rate, trades)
- Tax liability and transaction-cost panels
- Equity curve vs benchmark chart

### 5) Benchmark comparison tab (`CompareTab`)

Implemented:

- Benchmark summary fetch (`GET /api/v1/benchmarks/summary`)
- Strategy cards with type/proxy metadata
- Return vs drawdown and sharpe comparison charts
- 10-year projected growth line chart
- Metrics table and benchmark construction notes

### 6) AI chat widget (`AIChat`)

Implemented:

- Floating chat launcher
- Message history and typing state
- Chat endpoint integration (`POST /api/v1/explain/chat`)
- Context injection from current portfolio state
- Graceful fallback response on API failure

### 7) Frontend API layer (`src/services/backendApi.ts`)

Implemented adapters for:

- Portfolio generation
- Holdings analysis
- Backtesting
- Benchmark comparison
- Current model status
- Market data summary

This layer handles request/response shape mapping between backend DTOs and frontend typed models.

### 8) Local deterministic fallback/service logic

Local services still exist and are used for utility and fallback behavior:

- `portfolioService.ts`: risk profiles, allocation model types, fee/tax constants, local rule-based generation and analysis helpers
- `backtestEngine.ts`: legacy GBM-based offline backtest engine (marked as legacy note)
- `benchmarkService.ts`: local deterministic benchmark strategy set and growth projection helpers
- `localAdvisor.ts`: deterministic text insight/advice functions

### 9) Styling and design system (`src/index.css`)

Implemented:

- Theme variables and typography tokens
- Sidebar/topbar shell tokens (`--sidebar-w`, `--topbar-h`)
- Card/button/badge/input primitives
- Chart and table utility classes
- Chat UI, step indicators, and status chips

Note: the prior CSS parser crash caused by a broken font token has been fixed.

## Current Product Flow

1. User opens app -> sees sidebar shell with primary navigation.
2. In `Portfolio`, user chooses capital + risk and generates model-backed allocations.
3. User reviews metrics, sector diversification, and AI-generated portfolio explanation.
4. In `Trade Ideas`, user tests a holdings basket and receives diversification + rebalancing guidance.
5. In `Backtest`, user runs historical simulation with model variant and trading-rule knobs.
6. In `Compare`, user evaluates strategies across return, risk, drawdown, and projected growth.
7. At any point, user can open the AI assistant for guided questions.

## What Is Placeholder / In Progress

- `Market` tab currently renders placeholder cards (structure is ready, live wiring pending).
- Some UI labels are stage labels rather than fully dynamic data in sidebar footer.
- Components contain a mix of dark-theme utility classes and light Tailwind-like classes; functional, but not yet fully unified.

## Tech Stack

- Frontend: React 19 + TypeScript + Vite
- Charts: Recharts
- Icons: Lucide React
- API: FastAPI (local service in `apps/api`)
- Data/infra references: Postgres + Redis (for API runtime)

## Repository Structure

```text
.
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── components/
│   │   ├── GenerateTab.tsx
│   │   ├── AnalyzeTab.tsx
│   │   ├── BacktestTab.tsx
│   │   ├── CompareTab.tsx
│   │   ├── AIChat.tsx
│   │   └── MetricCard.tsx
│   ├── services/
│   │   ├── backendApi.ts
│   │   ├── portfolioService.ts
│   │   ├── backtestEngine.ts
│   │   ├── benchmarkService.ts
│   │   └── localAdvisor.ts
│   └── data/
│       └── stocks.ts
└── apps/api/
    └── README.md
```

## API Endpoints Used by Frontend

| Method | Endpoint | Used In |
|---|---|---|
| `GET` | `/api/v1/models/current` | Portfolio tab, Backtest tab |
| `GET` | `/api/v1/market-data/summary` | Backtest tab |
| `POST` | `/api/v1/portfolio/generate` | Portfolio generation |
| `POST` | `/api/v1/analysis/portfolio` | Trade Ideas / holdings analysis |
| `POST` | `/api/v1/backtests/run` | Backtesting |
| `GET` | `/api/v1/benchmarks/summary` | Compare tab |
| `POST` | `/api/v1/explain/portfolio` | Portfolio AI explanation |
| `POST` | `/api/v1/explain/chat` | Floating AI assistant |

## Local Setup

### Frontend

```bash
cd capstone
npm install
npm run dev
```

Default frontend URL: [http://localhost:3000](http://localhost:3000)

### Backend (summary)

Detailed backend setup is in `apps/api/README.md`.

Quick path:

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Optional environment variable

If backend runs elsewhere:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## npm Scripts

- `npm run dev` - start Vite dev server on port 3000
- `npm run build` - production build
- `npm run preview` - preview built app
- `npm run lint` - TypeScript no-emit check

## Known Notes

- The frontend is strongly API-coupled; if backend endpoints are unavailable, relevant panels show warning notices.
- Data in `src/data/stocks.ts` is a curated local universe used for local mapping/search and fallback utilities.
- Backtest, benchmark, and advisory local services remain in repo and are useful for deterministic/offline behavior, but main UI path prefers backend endpoints.
