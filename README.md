# NSE AI Trading Co-pilot

An industry-grade, Dockerized AI-powered NSE portfolio management system built as an MBA capstone project. Demonstrates supervised learning, sequence models, graph neural networks, and LLM reasoning in a single working product.

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Data | PostgreSQL/TimescaleDB | 3M+ NSE daily bars (2019–2026) |
| ML | LightGBM + LSTM + GNN + Death-Risk | Ensemble alpha scoring |
| LLM | Groq (Llama 3.3 70B) | Natural language explanations |
| API | FastAPI | REST backend |
| Frontend | React + Vite + TypeScript | Portfolio UI |

## ML Pipeline

1. **LightGBM** — Walk-forward cross-validated alpha model (31 features, 26k+ training rows)
2. **Bidirectional LSTM** — 20-day sequence model for temporal price patterns
3. **GNN (PyTorch Geometric)** — Sector relationship graph, 16-dim stock embeddings
4. **Death-Risk Classifier** — XGBoost, CV AUC 0.79, penalises crash-prone stocks
5.e Scorer** — `final = 0.65×z(LGB) + 0.20×z(GNN) - 1.5×death_risk`

## Quickstart
```bash
# 1. Start all services
docker compose up -d

# 2. Open frontend
open http://localhost:3000

# 3. API docs
open http://localhost:8000/docs
```

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/portfolio/generate | Generate AI portfolio |
| POST | /api/v1/analysis/portfolio | Analyse holdings |
| POST | /api/v1/backtests/run | Run backtest |
| GET | /api/v1/benchmarks/summary | Benchmark comparison |
| POST | /api/v1/explain/stock | Groq LLM stock explanation |
| POST | /api/v1/explain/chat | Groq LLM chat assistant |
| POST | /api/v1/explain/portfolio | Groq LLM portfolio analysis |
| GET | /api/v1/news/market-context | Market sentiment |
| GET | /api/v1/stock/{symbol} | Stock detail + ensemble scores |

## Retrain Models
```bash
# LightGBM
docker compose exec api bash -c "cd /app && PYTHONPATH=/app python scripts/ml/train_lightgbm_model.py \
  --datasetartifacts/datasets/lightgbm_v1/ml_dataset.csv \
  --dataset-manifest-json artifacts/datasets/lightgbm_v1/dataset_manifest.json \
  --artifact-dir artifacts/models/lightgbm_v1 \
  --initial-train-decision-dates 150 --val-decision-dates 50 --test-decision-dates 50 --embargo-decision-dates 2"

# LSTM
docker compose exec api bash -c "cd /app && PYTHONPATH=/app python scripts/ml/train_lstm_model.py \
  --start-date 2019-01-01 --end-date 2025-12-31 --max-symbols 100 --epochs 30 \
  --hidden-dim 64 --initial-train-samples 2000 --artifact-dir artifacts/models/lstm_v1"

# GNN
docker compose exec api bash -c "cd /app && PYTHONPATH=/app python scripts/ml/train_gnn_model.py \
  --max-symbols 100 --epochs 150 --hidden-dim 32 --out-dim 16 --artifact-dir artifacts/models/gnn_v1"
```

## Project Structure
```
apps/api/app/
├── api/routes/        # FastAPI route handlers
├── ml/                # LightGBM, LSTM, GNN, Death-risk, Ensemble
├── services/          # Portfolio engine, Groq explainer, News
└─ SQLAlchemy ORM models
src/
├── components/        # React tabs: Generate, Analyze, Backtest, Compare
└── services/          # API adapters
```
