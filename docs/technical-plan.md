# NSE AI Portfolio Manager Technical Plan

## 1. Current Codebase Assessment

What already exists in this repository:
- A strong frontend shell built with Vite + React and organized into four useful workflows: portfolio generation, portfolio analysis, backtesting, and benchmarking.
- A static NSE-oriented stock universe with sector metadata, beta, market-cap bucket, and simple proxy fundamentals.
- A portfolio construction service that already maps three user risk modes to different stock mixes.
- A backtesting service that already models stop-loss, take-profit, transaction costs, and tax buckets at a prototype level.
- A benchmarking view that compares the in-app strategy against common quant/index styles.

Main gaps before this can be considered a real quant product:
- Portfolio generation is rule-based and hardcoded, not optimizer-driven.
- Correlation and diversification logic use a hand-authored sector matrix instead of empirical return covariance.
- Backtesting uses simulated GBM paths instead of historical NSE candles adjusted for corporate actions.
- Benchmarks are hardcoded and not computed from index or factor histories.
- There is no backend, no persistent database, no market-data ingestion layer, no order ledger, and no tax-lot engine.
- The previous AI layer depended on Google AI Studio / Gemini instead of being local-first.

What was changed in this repo now:
- Removed the Google AI Studio / Gemini dependency from the app.
- Replaced it with a local advisory service in `src/services/localAdvisor.ts`.
- Simplified local runtime config and docs so the app can run without API keys.
- Added lazy-loaded tab modules to reduce the initial bundle.

## 2. System Architecture & Tech Stack

### Recommended target architecture

Use a split architecture:
- Frontend: React 19 + Vite + TypeScript
- API layer: Python `FastAPI`
- Quant engine: Python package inside the backend repo for factor models, optimization, risk, and backtests
- Database: PostgreSQL + TimescaleDB extension
- Analytics lakehouse: Parquet files + DuckDB/Polars for offline research and training
- Cache/queue: Redis
- Background jobs: Celery or Dramatiq workers
- Object storage: MinIO locally, S3 in production
- Local LLM option: Ollama-hosted model for explainability summaries only, not for final portfolio decisions

### Why this stack

Frontend:
- Keep the existing React/Vite app. It is already usable and fast for analytics-heavy UI.
- Add React Router, TanStack Query, and Zod once the backend API is introduced.

Backend:
- Move quant logic from TypeScript into Python because the ecosystem for portfolio optimization, factor research, statistical learning, and backtesting is materially better.
- Expose only stable API contracts to the frontend: portfolio generation, analyzer, benchmark runs, backtest submission, and scenario reports.

Database:
- PostgreSQL stores users, portfolios, holdings, orders, rebalancing plans, benchmark runs, tax lots, and audit logs.
- TimescaleDB stores daily and intraday bars, factor snapshots, volatility surfaces, and benchmark series.
- DuckDB + Parquet supports research notebooks, rolling feature generation, and fast local offline experiments without stressing the OLTP database.

Cloud and local setup:
- Local development: Docker Compose with `frontend`, `api`, `worker`, `postgres`, `redis`, `minio`, and optional `ollama`.
- Production: AWS `ap-south-1` is the most practical choice for an India-focused deployment.
- Production services: ECS/Fargate for API and worker containers, RDS PostgreSQL, ElastiCache Redis, S3, CloudFront, CloudWatch, and Secrets Manager.

### Service boundaries

1. `frontend-web`
   - Portfolio wizard
   - Holdings analyzer
   - Backtest console
   - Benchmark dashboards
   - Explainability and chat UI

2. `portfolio-api`
   - Auth and user settings
   - Portfolio generation endpoint
   - Rebalancing recommendation endpoint
   - Holdings risk analytics endpoint
   - Benchmark reporting endpoint

3. `market-data-service`
   - Historical data ingestion
   - Corporate-action adjustment
   - Instrument master maintenance
   - Feature and factor materialization

4. `simulation-worker`
   - Backtests
   - Walk-forward evaluations
   - Monte Carlo shock tests
   - Tax-lot and transaction-cost replay

5. `research-lab`
   - Model training
   - Regime detection
   - Hyperparameter search
   - Benchmark calibration

## 3. Data Pipeline

### Data sources

Historical:
- NSE daily bhavcopy and index history
- NSE instrument master and corporate-action references
- Optional broker/vendor historical API for intraday bars
- Fundamentals from a licensed provider or broker-integrated vendor

Real-time:
- Broker APIs or licensed market-data vendor streams for quotes and LTP
- Do not rely on scraping for production execution or portfolio valuation

Alternative/reference datasets:
- Risk-free rate series
- INR macro indicators
- Sector and style index histories
- Corporate actions: splits, bonuses, dividends, mergers, symbol changes

### Pipeline stages

1. Raw ingestion
   - Pull bhavcopy, index files, symbol metadata, and corporate actions
   - Persist raw files to object storage by source/date

2. Normalization
   - Canonicalize symbols
   - Map old/new tickers
   - Standardize timezone and trading calendar
   - Deduplicate by `symbol + timestamp`

3. Adjustment
   - Adjust historical prices and volumes for splits, bonuses, and dividends
   - Maintain both raw and adjusted series

4. Validation
   - Missing bar checks
   - Zero/negative price checks
   - Extreme move flags
   - Volume anomaly flags
   - Holiday and truncated-session checks

5. Feature generation
   - Returns: 1D, 5D, 21D, 63D, 126D, 252D
   - Rolling volatility and downside deviation
   - Beta vs Nifty 50 and sector index
   - Momentum, quality, value, carry/dividend, liquidity, and drawdown features
   - Rolling covariance and shrinkage covariance matrices

6. Serving
   - Latest bars, factors, and covariances go into PostgreSQL/Timescale
   - Research snapshots go to Parquet for reproducible experiments

### Recommended storage model

Core tables:
- `instruments`
- `daily_bars`
- `intraday_bars`
- `corporate_actions`
- `fundamentals_snapshot`
- `factor_scores`
- `covariance_snapshot`
- `benchmark_series`
- `user_portfolios`
- `portfolio_holdings`
- `rebalance_plans`
- `orders`
- `fills`
- `tax_lots`
- `backtest_runs`
- `backtest_metrics`

## 4. AI/ML Modeling Strategy

### Portfolio generation engine

Use a layered decision system rather than one single model.

Layer 1: Universe construction
- Exclude illiquid, suspended, or event-distorted names
- Apply minimum average daily traded value thresholds
- Bucket by large/mid/small cap and sector

Layer 2: Alpha and stability scores
- Momentum score
- Quality score
- Value score
- Dividend/defensive score
- Liquidity score
- Earnings stability score

Layer 3: Risk model
- Empirical covariance matrix from adjusted returns
- Ledoit-Wolf shrinkage or Oracle Approximating Shrinkage
- Beta, volatility, factor exposure, and concentration constraints

Layer 4: Optimizer
- MVP: constrained mean-variance or mean-CVaR optimization
- Stronger choice: Hierarchical Risk Parity plus factor tilt overlay
- Optional overlay: Black-Litterman to temper unstable return forecasts

### Risk mode mapping

Ultra-low risk:
- Primary objective: capital preservation and low drawdown
- Eligible assets: liquid ETFs, gold ETF, low-beta large caps, high-dividend defensives, short-duration debt-equivalent products if permitted
- Constraints: tight max weight per name, high hedge floor, low target volatility

Low/moderate risk:
- Objective: balanced risk-adjusted return
- Eligible assets: large and mid-cap quality names with some hedge sleeve
- Constraints: sector caps, moderate turnover, moderate target volatility

High risk:
- Objective: aggressive growth with controlled blow-up risk
- Eligible assets: high-momentum mid/small caps, higher-beta cyclicals, selective thematic exposure
- Constraints: stronger stop-loss rules, liquidity filter, tighter single-name cap despite higher risk budget

### Regime detection

Use regime awareness before trying reinforcement learning.

Recommended sequence:
- Phase 1: rule-based volatility and trend regimes
- Phase 2: Hidden Markov Model or Markov-switching volatility state model
- Phase 3: gradient-boosted classifier for bullish, sideways, and stressed regimes using realized volatility, breadth, drawdown, and macro features

Regime outputs should change:
- Exposure ceilings
- Hedge allocation
- Rebalance cadence
- Stop-loss aggressiveness
- Factor preference

### Reinforcement learning

Do not use RL in the MVP.

Only consider RL after:
- Historical simulator is trustworthy
- Slippage and tax engine are validated
- Benchmark baselines are hard to beat
- Actions are constrained to interpretable overlays like rebalance timing or cash buffer control

### Explainability and local AI

The local LLM should never be the portfolio decision-maker.

Use it for:
- Human-readable portfolio explanation
- Rebalance rationale summaries
- Risk and tax explanation
- Portfolio Q&A over already computed analytics

Keep the numerical decision path deterministic and auditable.

## 5. Simulation Engine Logic

### Core simulation loop

For each backtest date:
1. Load adjusted prices, factor snapshot, benchmark state, and current holdings.
2. If it is a rebalance date, generate target weights from the portfolio model.
3. Translate target weights into orders using available cash and lot-size constraints.
4. Apply fill-price model and transaction costs.
5. Evaluate intraday or bar-based stop-loss / take-profit rules.
6. Update holdings, cash, tax lots, and exposure history.
7. Record daily NAV, drawdown, turnover, benchmark-relative return, and attribution.

### Fill-price and slippage model

Use:
- `fill_price_buy = reference_price * (1 + slippage(side, liquidity, volatility))`
- `fill_price_sell = reference_price * (1 - slippage(side, liquidity, volatility))`

Slippage should depend on:
- ADV participation
- spread bucket
- volatility bucket
- gap risk at stop-loss execution

### Cost model

Parameterize all charges by date and broker plan.

For a delivery equity trade:
- `turnover = quantity * fill_price`
- `brokerage = min(turnover * broker_rate, broker_cap_per_order)`
- `stt = turnover * stt_rate(side, asset_type, effective_date)`
- `exchange_txn = turnover * exchange_txn_rate(effective_date)`
- `sebi_fee = turnover * sebi_rate(effective_date)`
- `stamp_duty = is_buy ? turnover * stamp_rate(effective_date, state) : 0`
- `gst = 0.18 * taxable_fee_base`
- `net_buy_cash = turnover + brokerage + stt + exchange_txn + sebi_fee + stamp_duty + gst`
- `net_sell_cash = turnover - brokerage - stt - exchange_txn - sebi_fee - gst`

### Tax-lot engine

Use FIFO tax lots for each symbol.

For every sell:
1. Match sold shares against oldest open lots.
2. Compute holding period per lot.
3. Split gains into STCG and LTCG buckets by effective-date rules.
4. Apply annual LTCG exemption at the portfolio/account level.
5. Persist lot-level realized P&L for auditability.

### Stop-loss and take-profit logic

Rules:
- Hard stop-loss per position
- Trailing stop-loss for high-risk mode
- Take-profit bands for momentum names
- Portfolio-level drawdown circuit breaker

Execution realism:
- If only EOD bars are available, simulate barrier hits conservatively using `open/high/low/close`
- If stop triggers through a gap, execute at the worse of trigger price or next available open

### Backtest outputs

Required metrics:
- CAGR
- annualized volatility
- Sharpe
- Sortino
- Calmar
- max drawdown
- turnover
- hit ratio
- profit factor
- beta vs benchmark
- information ratio
- tax drag
- cost drag

### Benchmarking framework

Compare against:
- Nifty 50
- Nifty 500
- Equal Weight Nifty 50
- Minimum Variance
- Momentum factor
- Quality factor
- AMC-style multi-factor sleeve
- Simple MVO baseline

Use the same:
- investable universe
- rebalance schedule
- cost model
- tax model
- start and end dates

## 6. Development Phases

### Phase 0: Stabilize the prototype
- Keep the current React shell
- Move mock data into structured fixtures
- Add API client abstractions
- Freeze UX contracts for the four existing tabs

### Phase 1: Local-first backend MVP
- Add FastAPI service
- Add PostgreSQL + TimescaleDB
- Add Docker Compose
- Add daily NSE historical ingestion
- Expose `generate`, `analyze`, and `backtest` endpoints
- Replace static benchmark service with backend-computed metrics

### Phase 2: Real historical backtesting
- Replace GBM with real adjusted historical bars
- Add corporate-action adjustments
- Add benchmark history ingestion
- Add tax-lot ledger and dated fee tables
- Add walk-forward and rolling validation

### Phase 3: Quant portfolio engine
- Implement factor scoring
- Add shrinkage covariance
- Add optimizer with sector/name/risk constraints
- Add regime-aware overlays
- Add rebalancing optimizer with turnover penalty

### Phase 4: User portfolio analyzer
- Upload CSV or broker-export holdings
- Compute factor exposure, concentration, and correlation heatmap
- Generate buy/sell recommendations toward the chosen risk mode
- Add explainability reports and rebalance diff view

### Phase 5: Benchmarking and research console
- Compute Nifty and factor benchmark histories
- Add attribution by sector/factor/cash/hedge sleeve
- Add scenario library: COVID crash, 2022 inflation, election volatility, sector shock, rate shock

### Phase 6: Production readiness
- Auth, RBAC, audit logs
- Secrets management
- Data lineage
- Broker abstraction layer
- Monitoring, alerting, retry policies, and backfill tools
- Compliance guardrails and disclaimer workflows

### Phase 7: Advanced intelligence
- Optional local LLM via Ollama for explanations
- Personalized suitability constraints
- Tax-aware rebalancing optimizer
- Portfolio drift alerts
- Recommendation confidence intervals

## 7. Immediate Next Steps From This Repo

The most practical path forward from the current codebase is:

1. Preserve this frontend as the UI shell.
2. Introduce a Python backend and move all quant logic behind typed APIs.
3. Replace `src/data/stocks.ts` with ingested instrument and factor data.
4. Replace the simulated backtest path with historical NSE bars and benchmark histories.
5. Convert hardcoded benchmark assumptions into reproducible backend jobs.
6. Keep the new local advisor only as an explanation layer, not the core portfolio engine.
