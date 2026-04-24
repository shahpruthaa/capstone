# NSE Atlas

Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.

## What This Repo Contains

- `src/`: React + Vite frontend (Institutional Design System)
- `apps/api/`: FastAPI backend, ensemble runtime, and quant engine
- `docs/`: Technical architecture, proof notes, and roadmap
- `scripts/`: Validation and ingestion helpers
- `infra/docker/`: Full orchestration support

## Product Surface

The system exposes a data-dense, institutional-grade research interface with these primary workspaces:

- **Overview**: System health, ensemble readiness, and market regime metrics.
- **Market**: Factor weather, sector heatmaps, and news-driven context.
- **Portfolio**: Mandate-driven generation and manual holdings analysis.
- **Trade Ideas**: Quantitative entry/exit checklists and AI rationales.
- **Backtest**: High-fidelity historical replay with Indian taxes and fees.
- **Compare**: Strategy benchmarking against Nifty and factor proxies.

**Removed from the current product:**
- Chatbot / AI chat widget
- Events tab
- Rebalance portfolio tab
- Generate AI analysis panel (standalone)

## Architecture Highlights

### Frontend (React 19)
- **Local-First**: Graceful degradation to local logic when the API is unavailable.
- **Design System**: Matte-black "Apple x Bloomberg" aesthetic for high information density.
- **State**: Centralized `backendApi.ts` adapter for contract parity.

### Backend (FastAPI + Python)
- **Ensemble Scorer**: Heterogeneous blend of LightGBM, LSTM, and GNN signals.
- **Quant Engine**: Mean-variance inspired optimizer with whole-share allocation.
- **Market Fidelity**: Integrated tax (Budget 2024) and SEBI fee schedules.
- **Persistence**: TimescaleDB for high-performance time-series ingestion.

## Active API Endpoints

| Method | Endpoint | Purpose |
| ------ | -------- | ------- |
| `GET` | `/api/v1/models/current` | Model runtime and artifact readiness |
| `GET` | `/api/v1/market-data/summary` | Coverage and regime status |
| `POST` | `/api/v1/portfolio/generate` | Build ensemble-optimized baskets |
| `POST` | `/api/v1/backtests/run` | Execute friction-aware replay |
| `GET` | `/api/v1/trade-ideas` | High-conviction shortlist |
| `GET` | `/api/v1/news/market-context` | Real-time news sentiment and pulse |

## Local Setup

### Frontend
```bash
npm install
npm run dev
```

### Backend
```bash
cd apps/api
python -m venv .venv
# Activate venv and then:
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Validation & Quality

- `npm run build`: Enforces frontend production standards.
- `python -m py_compile ...`: Validates backend service integrity.
- `scripts/ui-smoke.py`: Automates cross-tab functional verification.

---
*NSE Atlas is designed for research and educational purposes. It does not provide financial advice or brokerage execution.*
