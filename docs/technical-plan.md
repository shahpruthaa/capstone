# NSE AI Portfolio Manager Technical Plan

## 1. Current State

This repository already contains a functioning end-to-end local research stack:

- React/Vite frontend
- FastAPI backend
- PostgreSQL + TimescaleDB persistence
- NSE bhavcopy ingestion
- DB-backed portfolio generation
- DB-backed analysis
- DB-backed backtests
- DB-backed benchmark summaries

For the current supported scope, the following items are now implemented end to end:

- expected return model
- tax model detail
- fee table detail by effective date
- rebalance policy

The remaining work is mostly about production depth, live data, and official benchmark replication.

## 2. Expected Return Model

### Inputs

- adjusted total-return histories
- aligned return matrix across selected instruments
- risk-mode configuration
- factor z-scores
- rule-based market regime

### Factor Set

- `momentum`
- `quality`
- `low_vol`
- `liquidity`
- `sector_strength`
- `size`
- `beta`

Current construction:

- `momentum = 0.20 * 1M + 0.35 * 3M + 0.45 * 6M`
- `quality = annual_return - 0.70 * downside_vol - 0.40 * max_drawdown + beta_discipline`
- `low_vol = -annual_volatility`
- `liquidity = sqrt(avg_traded_value)`
- `sector_strength = stock_momentum - sector_average_momentum`
- `size = {Large: 1, Mid: 0, Small: -1, Unknown: -0.25}`
- `beta = beta_proxy - 1`

### Regime Overlay

Current overlay is simple and deterministic:

- benchmark trend weak or volatility stressed -> defensive base return
- benchmark trend strong and volatility controlled -> risk-on bonus
- otherwise neutral

### Risk-Mode Return Blends

#### Ultra-Low

- regime base return
- `0.30 * annual_mean`
- `0.028 * factor_alpha`
- defensive / ETF bonus

#### Moderate

- regime base return
- `0.36 * annual_mean`
- `0.030 * factor_alpha`

#### High

- regime base return
- regime risk-on bonus
- `0.42 * annual_mean`
- `0.035 * factor_alpha`
- cyclical bonus

### Guardrails

- beta drift penalty
- bounded output clamp before optimization

Implementation status:

- Complete for current scope

Known boundary:

- no fundamentals-driven quality/value factors yet

## 3. Tax Model Detail

### Supported Scope

- listed delivery-equity research simulation

### Lot Logic

- FIFO tax lots per symbol
- realized gains bucketed by:
  - financial year
  - holding period
  - effective tax schedule

### Holding Period Rules

- `STCG`: `< 365 days`
- `LTCG`: `>= 365 days`

### Effective-Date Tax Schedules

| Effective From | STCG | LTCG | LTCG Exemption | Cess |
| --- | --- | --- | --- | --- |
| `2020-07-01` | `15%` | `10%` | `Rs 1,00,000` | `4%` |
| `2024-07-23` | `20%` | `12.5%` | `Rs 1,25,000` | `4%` |

### Computation Sequence

1. realize lots using FIFO
2. bucket gains by fiscal year and schedule
3. apply STCG only on positive net STCG
4. net positive and negative LTCG inside fiscal-year schedule buckets
5. apply LTCG exemption once per fiscal year
6. compute cess on base tax

### Output Fields

- `stcg_gain`
- `ltcg_gain`
- `stcg_tax`
- `ltcg_tax`
- `cess_tax`
- `total_tax`

Implementation status:

- Complete for current scope

Known boundary:

- no surcharge
- no derivatives tax support

## 4. Fee Table Detail by Effective Date

### Per-Trade Formula

- `brokerage = min(turnover * brokerage_rate, max_brokerage_per_order)`
- `stt = turnover * stt_rate(side)`
- `stamp_duty = turnover * stamp_duty_buy_rate` on buy only
- `exchange_txn = turnover * exchange_txn_rate`
- `sebi_fee = turnover * sebi_fee_rate`
- `gst = (brokerage + exchange_txn + sebi_fee) * gst_rate`
- `slippage = turnover * liquidity_adjusted_slippage_rate`
- `total_costs = sum(all components)`

### Effective-Date Fee Schedules

| Effective From | Brokerage | Max Brokerage | STT Buy | STT Sell | Exchange Txn | SEBI | Stamp Duty Buy | GST |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `2020-07-01` | `0.03%` | `Rs 20` | `0.10%` | `0.10%` | `0.00297%` | `0.00010%` | `0.015%` | `18%` |
| `2024-07-23` | `0.03%` | `Rs 20` | `0.10%` | `0.10%` | `0.00297%` | `0.00010%` | `0.015%` | `18%` |

### Slippage Model

- liquidity participation based
- volatility loaded
- engineering cap applied

Implementation status:

- Complete for current scope

Known boundary:

- no broker-plan-specific schedules

## 5. Rebalance Policy

### Review Cadence

- monthly = `21` trading days
- quarterly = `63` trading days
- annually = `252` trading days
- none = disabled

### Risk-Mode Rules

| Risk Mode | Drift Threshold | Minimum Trade Weight | Cooldown After Exit |
| --- | --- | --- | --- |
| `ULTRA_LOW` | `6.0%` | `3.0%` | `5 days` |
| `MODERATE` | `4.0%` | `2.5%` | `7 days` |
| `HIGH` | `3.0%` | `2.0%` | `10 days` |

### Decision Logic

1. generate current optimizer target
2. compare live holdings with target weights
3. sell overweights if drift exceeds threshold
4. buy underweights only if:
   - cash is available
   - symbol is out of cooldown
   - minimum trade budget is met

Implementation status:

- Complete for current scope

Known boundary:

- no persisted approval workflow
- no user-custom rebalance policy editor yet

## 6. End-to-End Flow

### Portfolio Generation

1. load instruments and histories from the database
2. apply corporate-action adjustment if actions exist
3. compute factor scores
4. estimate expected returns
5. estimate shrinkage covariance
6. optimize long-only constrained portfolio
7. persist run and return notes to the UI

### Holdings Analysis

1. price holdings from the database
2. compute sector weights, beta, factor exposures, and correlation
3. generate optimizer target for the chosen risk mode
4. compute target-vs-current rebalance actions
5. return notes and actions to the UI

### Backtest

1. generate starting portfolio from historical data available at start date
2. load adjusted daily OHLC history and dividend cash events
3. enter positions with dated fee schedules
4. simulate stop-loss, take-profit, and rebalance events
5. realize gains via FIFO lots
6. compute STCG/LTCG/cess under the correct effective schedule
7. persist results and render them in the UI

## 7. Documentation / Code Mapping

Primary implementation files:

- [db_quant_engine.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/db_quant_engine.py)
- [market_rules.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/market_rules.py)
- [corporate_actions.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/services/corporate_actions.py)
- [portfolio.py](C:/Users/pruth/nse-ai-portfolio-manager/apps/api/app/schemas/portfolio.py)

UI surfaces:

- [GenerateTab.tsx](C:/Users/pruth/nse-ai-portfolio-manager/src/components/GenerateTab.tsx)
- [AnalyzeTab.tsx](C:/Users/pruth/nse-ai-portfolio-manager/src/components/AnalyzeTab.tsx)
- [BacktestTab.tsx](C:/Users/pruth/nse-ai-portfolio-manager/src/components/BacktestTab.tsx)
- [CompareTab.tsx](C:/Users/pruth/nse-ai-portfolio-manager/src/components/CompareTab.tsx)

## 8. Phase Status

| Phase | Scope | Status | Notes |
| --- | --- | --- | --- |
| 0 | UI shell | Complete | browser workflows are live |
| 1 | Local backend | Complete | API, Docker, Postgres, Redis |
| 2 | Historical ingestion | Complete | bhavcopy + raw cache + Timescale daily bars |
| 3 | Expected return + allocator | Complete for current scope | factor-aware alpha + shrinkage covariance + constraints |
| 4 | Tax/fees/rebalance | Complete for current scope | FIFO tax lots, dated fee schedules, drift-based rebalance |
| 5 | Simulation realism | Partial | daily OHLC only, not intraday |
| 6 | Benchmarking | Partial | proxy benchmarks only |
| 7 | Live / production hardening | Not started | live feeds, broker routing, auth, compliance |

## 9. Remaining Backlog

The four requested areas are complete for the current supported local research scope. The remaining work is:

- official benchmark constituent ingestion
- live market-data feeds
- fundamentals-driven factor models
- intraday execution modeling
- broker-specific fee plans
- user portfolio persistence and approval flows
