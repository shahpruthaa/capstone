# NSE Atlas Technical Plan

## Goal

Maintain the system as a stable, research-grade, local-first analytics engine with:

- multi-model ensemble intelligence (LGBM, LSTM, GNN)
- high-fidelity friction-aware backtesting
- mandate-driven portfolio optimization
- institutional-grade UI density and transparency

## Current Status

| Workstream | Status | Outcome |
| ---------- | ------ | ------- |
| Runtime status reporting | Complete | Full transparency on model readiness and artifact versions |
| Ensemble generation path | Complete | Generation uses active ensemble scores with regime-aware weighting |
| Mandate logic overhaul | Complete | User horizon and risk attitude now strictly control optimizer constraints |
| Diversification guards | Complete | Hard caps on sector and single-name concentration in the engine |
| Backtest fidelity | Complete | Integrated Budget 2024 tax schedules and tiered NSE fee structures |
| Product surface cleanup | Complete | Removed chatbot, events tab, and legacy rebalance workflows |
| News Intelligence | Partial | Sector-level news sentiment pulse is integrated but lacks deep history |
| Production Stability | Complete | `npm run build` and backend compile checks are green |

## Core Workflow

1. **System Audit**: Verify ensemble health and market regime status.
2. **Strategy Generation**: Build portfolios using quantitative mandates.
3. **Institutional Analysis**: Review allocations, risk scores, and AI rationales.
4. **Historical Replay**: Run backtests with realistic implementation costs.
5. **Alpha Benchmarking**: Compare AI strategies against Nifty and factor proxies.

## Validation Plan

- **Frontend**: Enforce `npm run build` before every release to catch CSS/Type regressions.
- **Backend**: Use `py_compile` on `db_quant_engine.py` and `ensemble_scorer.py` for syntax integrity.
- **Integration**: Run `scripts/ui-smoke.py` to ensure cross-tab data flow remains intact.

## Remaining Work

1. **Artifact Retraining**: Refresh local `.lgb` and `.pt` weights with 2024-2025 market data.
2. **Automated Fixtures**: Implement database fixtures for more robust integration testing.
3. **Advanced Attribution**: Decompose backtest returns into factor exposures (Momentum vs Quality).
4. **Performance**: Optimize TimescaleDB indexes for faster multi-year historical ingestion.
