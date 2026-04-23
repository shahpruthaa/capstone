# NSE Atlas Technical Plan

## Goal

Operate a stable local-first research stack where:

- portfolio generation, analysis, and backtests are backend-authoritative
- frontend surfaces stay aligned with backend contracts
- runtime/scheduler/ingestion behavior is explicit and observable
- merged branch logic remains traceable and testable

## Current State (Post-Merge)

| Workstream                                     | Status         | Notes                                                                                                        |
| ---------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------ |
| Core ensemble engine preservation              | Complete       | `db_quant_engine`, `decision_engine`, `price_levels`, `ensemble_scorer` preserved from `kairavee-improv`     |
| Frontend reintroduction from `kairavee-improv` | Complete       | Current `src/*` surface rebuilt from feature branch in a dedicated follow-up commit                          |
| Route/schema expansion                         | Active in main | Main keeps richer contracts for benchmarks compare, market regime, trade-ideas screening, and model overview |
| Scheduler lifecycle integration                | Complete       | Startup + shutdown wiring in `app.main` with `APP_SCHEDULER_ENABLED` gate                                    |
| Market-calendar-aware ingestion                | Complete       | Trading-day checks no longer rely only on weekday logic                                                      |
| Frontend production build                      | Passing        | `npm run build` currently green                                                                              |
| Backend test portability                       | Partial        | DB-backed tests still depend on local Postgres availability                                                  |

## Current Product Flow

1. View `Overview` for model/runtime/health signals.
2. Use `Portfolio` workspace to either build a mandate-driven basket or analyze existing holdings.
3. Inspect `Trade Ideas` and optional screening path.
4. Run `Backtest` against historical data.
5. Use `Compare` for benchmark-relative performance views.
6. Use `Market` for regime and context dashboards.

## Backend Plan (Now)

Primary code paths:

- `apps/api/app/services/db_quant_engine.py`
- `apps/api/app/services/decision_engine.py`
- `apps/api/app/services/ensemble_scorer.py`
- `apps/api/app/services/model_overview.py`

Design intent:

- Keep engine computations and constraints in backend services.
- Keep route handlers thin and schema-driven.
- Keep runtime/scheduler behavior explicit and toggleable by config.

## Frontend Plan (Now)

Primary contract adapter:

- `src/services/backendApi.ts`

Primary surface:

- `Overview`, `Market`, `Portfolio`, `Trade Ideas`, `Backtest`, `Compare`

Non-goals for the current baseline:

- reintroducing removed chat/events/rebalance surfaces
- adding parallel API clients per tab (single adapter remains preferred)

## Documentation/Contract Plan

This update aligns docs with the live route/surface set and removes stale references.

Contract-sensitive areas to keep synchronized whenever changed:

- `apps/api/app/schemas/portfolio.py`
- `apps/api/app/schemas/trade_idea.py`
- `apps/api/app/api/routes/*.py`
- `src/services/backendApi.ts`

## Validation Plan

Required on each merge/update:

- `npm run build`
- `npm run lint`
- syntax checks for touched backend services/routes (`py_compile`)
- route-level smoke via `/docs` and selected endpoint calls where DB is available

Optional but recommended when DB is running:

- `pytest apps/api/test_portfolio_gen.py -q`

## Risks and Mitigations

- Risk: API/schema drift between backend and frontend.
  Mitigation: keep changes centralized in `backendApi.ts` and schema modules.

- Risk: Scheduler side effects in dev.
  Mitigation: `APP_SCHEDULER_ENABLED` toggle and explicit shutdown handler.

- Risk: Data-dependent false negatives in tests.
  Mitigation: document DB prerequisites and keep deterministic fixture-based tests as follow-up.

## Next Engineering Steps

1. Add DB fixture-backed integration tests for generate/analyze/backtest/trade-ideas flows.
2. Add API contract snapshot tests for key response models.
3. Reduce frontend bundle size via route-level/code-level splitting where practical.
