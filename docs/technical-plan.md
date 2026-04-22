# NSE Atlas Technical Plan

## Goal

Keep the current product stable as a local-first research app with:

- ensemble-aware portfolio generation
- reliable holdings analysis
- diversified portfolio construction
- runtime transparency
- repeatable frontend validation

## Current Status

| Workstream | Status | Outcome |
| ---------- | ------ | ------- |
| Runtime status reporting | Complete | UI and backend share the same readiness view |
| Ensemble generation path | Complete | Generation uses the ensemble runtime with sufficient feature history |
| Mandate horizon separation | Complete | Horizon now controls decision logic, not feature truncation |
| Portfolio diversification controls | Complete | Name and sector concentration are capped during selection and weighting |
| Holdings analysis hardening | Complete | Direct symbol entry, longer timeout, backend notes, and local fallback are in place |
| Product-surface cleanup | Complete | Chatbot, events, rebalance tab, and generated AI analysis were removed |
| Frontend production build | Complete | `npm run build` passes |
| Live backend DB verification | Partial | Blocked when PostgreSQL is unavailable |

## Product Flow

The intended user flow is:

1. inspect runtime state
2. generate a mandate-driven portfolio
3. review allocations and diversification
4. analyze current holdings
5. run backtests
6. compare strategies

## Backend Plan

The backend continues to center on:

- `db_quant_engine.py`
- `ensemble_scorer.py`
- `model_runtime.py`

Current expectations:

- generation should fail clearly when the requested ensemble runtime is unusable
- holdings analysis should prefer the backend path but degrade gracefully
- diversification logic should be enforced in the engine rather than assumed in the UI

## Frontend Plan

The frontend is now intentionally narrower:

- no chatbot
- no events tab
- no rebalance portfolio tab
- no generate AI analysis panel

That keeps the product focused on the workflows that still have strong backend support.

## Validation Plan

Primary checks:

- `npm run build`
- backend `py_compile` on edited services and routes
- targeted repo-wide search for stale removed-feature references

Environmental dependency:

- live portfolio generation and holdings analysis still require PostgreSQL access

## Remaining Work

Still worth improving later:

- stronger automated backend integration tests with database fixtures
- chunk splitting for the large frontend production bundle
- fresh artifact retraining and validation
