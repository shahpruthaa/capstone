from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from math import sqrt
from statistics import median
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.backtest_run import BacktestRun
from app.models.daily_bar import DailyBar
from app.models.generated_portfolio_run import GeneratedPortfolioAllocation, GeneratedPortfolioRun
from app.models.instrument import Instrument
from app.schemas.portfolio import (
    AllocationModel,
    AnalyzePortfolioRequest,
    AnalyzePortfolioResponse,
    BacktestMetricModel,
    BacktestRequest,
    BacktestResultResponse,
    BenchmarkGrowthPointModel,
    BenchmarkMetricModel,
    BenchmarkSummaryResponse,
    CostBreakdownModel,
    CurvePointModel,
    GeneratePortfolioRequest,
    GeneratePortfolioResponse,
    PortfolioMetricsModel,
    RebalanceActionModel,
    TaxBreakdownModel,
)


BROKERAGE_RATE = 0.0003
MAX_BROKERAGE = 20.0
STT_BUY_RATE = 0.001
STT_SELL_RATE = 0.001
STAMP_DUTY_RATE = 0.00015
GST_RATE = 0.18
SLIPPAGE_RATE = 0.001
RISK_FREE_RATE = 0.07
DEFAULT_BACKTEST_INVESTMENT = 1_000_000.0

RISK_MODE_UNIVERSES = {
    "ULTRA_LOW": ["LIQUIDBEES", "GOLDBEES", "NIFTYBEES", "HDFCBANK", "ITC", "SUNPHARMA", "POWERGRID", "BHARTIARTL", "NTPC"],
    "MODERATE": ["HDFCBANK", "ICICIBANK", "TCS", "INFY", "RELIANCE", "SUNPHARMA", "HINDUNILVR", "BHARTIARTL", "GOLDBEES", "LIQUIDBEES", "LT", "POWERGRID", "CIPLA", "SBIN"],
    "HIGH": ["TATAMOTORS", "COFORGE", "KPITTECH", "ADANIGREEN", "ZOMATO", "PERSISTENT", "DLF", "MUTHOOTFIN", "BHEL", "DIVISLAB", "INDUSINDBK", "GOLDBEES"],
}

RISK_MODE_TARGET_SECTORS = {
    "ULTRA_LOW": {"Liquid": 30.0, "Gold": 18.0, "FMCG": 12.0, "Pharma": 12.0, "Banking": 10.0, "Energy": 10.0, "Telecom": 8.0},
    "MODERATE": {"Banking": 16.0, "IT": 16.0, "Energy": 12.0, "Pharma": 10.0, "FMCG": 10.0, "Gold": 8.0, "Liquid": 8.0, "Telecom": 8.0, "Infra": 12.0},
    "HIGH": {"IT": 20.0, "Auto": 14.0, "Energy": 15.0, "Tech/Internet": 10.0, "Finance": 10.0, "Infra": 10.0, "Pharma": 8.0, "Real Estate": 8.0, "Banking": 5.0},
}

BENCHMARK_UNIVERSES = [
    ("NSE AI Portfolio", "AI", "Correlation-aware diversified risk-mode strategy."),
    ("Nifty 50", "INDEX", "ETF-based large-cap benchmark proxy using Nifty 50 exposure."),
    ("Nifty 500", "INDEX", "Broad equal-weight listed-universe proxy from ingested securities."),
    ("Momentum Basket", "FACTOR", "Top-momentum NSE basket using trailing return strength."),
    ("AMC Multi Factor", "AMC_STYLE", "Balanced factor sleeve blending momentum, quality proxy, and lower volatility."),
]


@dataclass
class Snapshot:
    symbol: str
    name: str
    sector: str
    instrument_type: str
    market_cap_bucket: str | None
    latest_trade_date: date
    latest_price: float
    closes: list[tuple[date, float]]
    returns: list[tuple[date, float]]
    annual_return_pct: float
    annual_volatility_pct: float
    momentum_pct: float
    avg_traded_value: float
    beta_proxy: float = 1.0


def generate_portfolio(db: Session, payload: GeneratePortfolioRequest) -> GeneratePortfolioResponse:
    as_of_date = payload.as_of_date or get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, symbols=RISK_MODE_UNIVERSES[payload.risk_mode], min_history=40)
    if len(snapshots) < 4:
        snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=40)
    selected = select_portfolio_candidates(payload.risk_mode, snapshots)
    if not selected:
        raise ValueError("Not enough historical market data to generate a portfolio. Ingest bhavcopy data first.")

    weighted_stats = build_weighted_statistics(selected)
    notes = [
        f"Portfolio built from {len(selected)} instruments using prices through {as_of_date.isoformat()}.",
        "Weights are derived from trailing return, volatility, liquidity, and sector-diversification heuristics stored in PostgreSQL.",
        "This backend flow is now data-backed, but still a first-pass heuristic optimizer rather than a full covariance-constrained solver.",
    ]

    run = GeneratedPortfolioRun(
        risk_mode=payload.risk_mode,
        investment_amount=Decimal(str(round(payload.investment_amount, 2))),
        as_of_date=as_of_date,
        metrics_json=weighted_stats.model_dump(),
        notes="\n".join(notes),
    )
    db.add(run)
    db.flush()

    allocations: list[AllocationModel] = []
    for snapshot, weight in selected:
        rationale = build_rationale(snapshot, payload.risk_mode)
        db.add(
            GeneratedPortfolioAllocation(
                portfolio_run_id=run.id,
                symbol=snapshot.symbol,
                sector=snapshot.sector,
                weight=Decimal(str(round(weight, 4))),
                rationale=rationale,
            )
        )
        allocations.append(
            AllocationModel(
                symbol=snapshot.symbol,
                sector=snapshot.sector,
                weight=round(weight, 2),
                rationale=rationale,
            )
        )

    db.commit()
    return GeneratePortfolioResponse(
        risk_mode=payload.risk_mode,
        investment_amount=payload.investment_amount,
        allocations=allocations,
        metrics=weighted_stats,
        notes=notes,
    )


def analyze_portfolio(db: Session, payload: AnalyzePortfolioRequest) -> AnalyzePortfolioResponse:
    snapshots = load_snapshots(db, symbols=[holding.symbol for holding in payload.holdings], min_history=20)
    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots}

    total_value = 0.0
    sector_value: dict[str, float] = defaultdict(float)
    beta_numerator = 0.0
    priced_holdings = []
    missing_symbols = []

    for holding in payload.holdings:
        snapshot = snapshot_map.get(holding.symbol)
        if snapshot is None:
            missing_symbols.append(holding.symbol)
            continue
        value = snapshot.latest_price * holding.quantity
        total_value += value
        sector_value[snapshot.sector] += value
        beta_numerator += snapshot.beta_proxy * value
        priced_holdings.append((holding, snapshot, value))

    if total_value <= 0:
        raise ValueError("None of the submitted holdings have market data in the database yet.")

    sector_weights = {sector: round((value / total_value) * 100, 2) for sector, value in sector_value.items()}
    current_beta = round(beta_numerator / total_value, 2)
    avg_corr = average_pairwise_correlation([snapshot for _, snapshot, _ in priced_holdings])
    diversification_score = round(max(20.0, min(95.0, len(sector_weights) * 10 + (1 - avg_corr) * 45)), 1)

    correlation_risk = "LOW"
    if avg_corr >= 0.6:
        correlation_risk = "HIGH"
    elif avg_corr >= 0.35:
        correlation_risk = "MODERATE"

    target_sectors = RISK_MODE_TARGET_SECTORS[payload.target_risk_mode]
    actions = build_rebalance_actions(priced_holdings, sector_weights, target_sectors, payload.target_risk_mode, db)
    notes = [
        f"Analysis used latest close prices for {len(priced_holdings)} holdings from PostgreSQL.",
        f"Average pairwise trailing correlation across the priced holdings is {avg_corr:.2f}.",
    ]
    if missing_symbols:
        notes.append(f"No market data found yet for: {', '.join(sorted(set(missing_symbols)))}.")

    return AnalyzePortfolioResponse(
        total_holdings=len(payload.holdings),
        portfolio_value=round(total_value, 2),
        current_beta=current_beta,
        diversification_score=diversification_score,
        sector_weights=sector_weights,
        correlation_risk=correlation_risk,
        actions=actions,
        notes=notes,
    )


def run_backtest(db: Session, payload: BacktestRequest) -> BacktestResultResponse:
    snapshots = load_snapshots(db, as_of_date=payload.start_date, symbols=RISK_MODE_UNIVERSES[payload.risk_mode], min_history=40)
    if len(snapshots) < 4:
        snapshots = load_snapshots(db, as_of_date=payload.start_date, min_history=40)
    model_portfolio = select_portfolio_candidates(payload.risk_mode, snapshots)
    if not model_portfolio:
        raise ValueError("Not enough historical market data to backtest. Ingest bhavcopy data first.")

    weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in model_portfolio}
    price_map = load_close_matrix(db, list(weights.keys()), payload.start_date, payload.end_date)
    benchmark_symbol = select_benchmark_symbol(db)
    benchmark_map = load_close_matrix(db, [benchmark_symbol], payload.start_date, payload.end_date)
    all_dates = sorted({trade_date for symbol_prices in price_map.values() for trade_date in symbol_prices.keys()})
    if len(all_dates) < 2:
        raise ValueError("Backtest window does not have enough daily bars for the selected strategy.")

    position_state = initialize_positions(price_map, weights, all_dates[0], DEFAULT_BACKTEST_INVESTMENT)
    if not position_state:
        raise ValueError("Selected instruments do not have usable prices on the requested backtest start date.")
    equity_curve: list[CurvePointModel] = []
    costs = {key: 0.0 for key in ["total_brokerage", "total_stt", "total_stamp_duty", "total_gst", "total_slippage", "total_costs"]}
    taxes = {key: 0.0 for key in ["stcg_gain", "ltcg_gain", "stcg_tax", "ltcg_tax", "total_tax"]}
    portfolio_returns: list[float] = []
    prev_value = DEFAULT_BACKTEST_INVESTMENT
    total_trades = 0

    rebalance_interval = {"MONTHLY": 21, "QUARTERLY": 63, "ANNUALLY": 252, "NONE": 10**9}[payload.rebalance_frequency]
    benchmark_series = benchmark_map.get(benchmark_symbol, {})
    benchmark_first_price = benchmark_series.get(all_dates[0])

    for index, trade_date in enumerate(all_dates):
        for symbol, state in position_state.items():
            price = price_map[symbol].get(trade_date)
            if price is None or state["shares"] <= 0:
                continue
            return_pct = (price / state["entry_price"]) - 1
            should_exit = return_pct <= -payload.stop_loss_pct or return_pct >= payload.take_profit_pct
            if should_exit:
                proceeds = price * state["shares"]
                trade_costs = calculate_trade_costs(proceeds, is_buy=False)
                apply_costs(costs, trade_costs)
                gain = proceeds - state["cost_basis"]
                holding_days = (trade_date - state["entry_date"]).days
                if holding_days < 365:
                    taxes["stcg_gain"] += gain
                else:
                    taxes["ltcg_gain"] += gain
                state["cash_pool"][0] += proceeds - trade_costs["total_costs"]
                state["shares"] = 0
                state["cost_basis"] = 0.0
                total_trades += 1

        portfolio_value = position_state[next(iter(position_state))]["cash_pool"][0]
        for symbol, state in position_state.items():
            price = price_map[symbol].get(trade_date)
            if price is not None:
                portfolio_value += state["shares"] * price

        if index > 0 and index % rebalance_interval == 0 and payload.rebalance_frequency != "NONE":
            total_trades += rebalance_positions(position_state, price_map, weights, trade_date, portfolio_value, costs, taxes)
            portfolio_value = position_state[next(iter(position_state))]["cash_pool"][0]
            for symbol, state in position_state.items():
                price = price_map[symbol].get(trade_date)
                if price is not None:
                    portfolio_value += state["shares"] * price

        if index > 0:
            portfolio_returns.append((portfolio_value - prev_value) / max(prev_value, 1))
        prev_value = portfolio_value

        benchmark_value = DEFAULT_BACKTEST_INVESTMENT
        if benchmark_first_price:
            benchmark_price = benchmark_series.get(trade_date, benchmark_first_price)
            benchmark_value = DEFAULT_BACKTEST_INVESTMENT * (benchmark_price / benchmark_first_price)

        equity_curve.append(
            CurvePointModel(
                date=trade_date,
                portfolio_value=round(portfolio_value, 2),
                benchmark_value=round(benchmark_value, 2),
            )
        )

    ltcg_taxable = max(0.0, taxes["ltcg_gain"] - 125000.0)
    taxes["ltcg_tax"] = ltcg_taxable * 0.125
    taxes["stcg_tax"] = max(0.0, taxes["stcg_gain"]) * 0.20
    taxes["total_tax"] = taxes["ltcg_tax"] + taxes["stcg_tax"]

    metrics = build_backtest_metrics(equity_curve, portfolio_returns, costs, taxes, total_trades)
    run_id = f"bt-{uuid4()}"
    notes = [
        f"Historical replay used {len(weights)} data-backed instruments between {payload.start_date.isoformat()} and {payload.end_date.isoformat()}.",
        "Stop-loss and take-profit were evaluated on daily closes with fee and tax drag applied to each realized trade.",
    ]

    db.add(
        BacktestRun(
            id=run_id,
            strategy_name=payload.strategy_name,
            risk_mode=payload.risk_mode,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status="completed",
            metrics_json={
                "metrics": metrics.model_dump(),
                "tax_liability": round_mapping(taxes),
                "cost_breakdown": round_mapping(costs),
                "equity_curve": [point.model_dump() for point in equity_curve],
                "notes": notes,
            },
            notes="\n".join(notes),
        )
    )
    db.commit()

    return BacktestResultResponse(
        run_id=run_id,
        status="completed",
        metrics=metrics,
        tax_liability=TaxBreakdownModel(**round_mapping(taxes)),
        cost_breakdown=CostBreakdownModel(**round_mapping(costs)),
        equity_curve=equity_curve,
        notes=notes,
    )


def get_backtest_result(db: Session, run_id: str) -> BacktestResultResponse:
    run = db.get(BacktestRun, run_id)
    if run is None:
        raise ValueError(f"Backtest run {run_id} was not found.")
    payload = run.metrics_json
    return BacktestResultResponse(
        run_id=run.id,
        status="completed",
        metrics=BacktestMetricModel(**payload["metrics"]),
        tax_liability=TaxBreakdownModel(**payload["tax_liability"]),
        cost_breakdown=CostBreakdownModel(**payload["cost_breakdown"]),
        equity_curve=[CurvePointModel(**point) for point in payload["equity_curve"]],
        notes=payload["notes"],
    )


def get_benchmark_summary(db: Session) -> BenchmarkSummaryResponse:
    as_of_date = get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=120)
    if not snapshots:
        raise ValueError("No benchmark data is available yet. Ingest bhavcopy data first.")

    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots}
    benchmark_portfolios = {
        "NSE AI Portfolio": dict((snapshot.symbol, weight / 100.0) for snapshot, weight in select_portfolio_candidates("MODERATE", snapshots)),
        "Nifty 50": build_named_weights(snapshot_map, [select_benchmark_symbol(db)]),
        "Nifty 500": build_equal_weight_portfolio(snapshots, 20),
        "Momentum Basket": build_ranked_portfolio(snapshots, key=lambda snapshot: snapshot.momentum_pct, descending=True, count=8),
        "AMC Multi Factor": build_ranked_portfolio(
            snapshots,
            key=lambda snapshot: (snapshot.annual_return_pct / max(snapshot.annual_volatility_pct, 1.0)) + (snapshot.momentum_pct / 25.0) - (snapshot.beta_proxy / 10.0),
            descending=True,
            count=8,
        ),
    }

    strategies = []
    for name, category, description in BENCHMARK_UNIVERSES:
        metrics = summarize_return_series(aggregate_portfolio_returns(snapshot_map, benchmark_portfolios.get(name, {})))
        strategies.append(
            BenchmarkMetricModel(
                name=name,
                description=description,
                category=category,  # type: ignore[arg-type]
                annual_return_pct=metrics["annual_return_pct"],
                volatility_pct=metrics["volatility_pct"],
                sharpe_ratio=metrics["sharpe_ratio"],
                sortino_ratio=metrics["sortino_ratio"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                cagr_5y_pct=metrics["cagr_pct"],
                expense_ratio_pct=0.08 if category == "AI" else 0.05 if category == "INDEX" else 0.32,
            )
        )

    projected_growth = []
    initial_amount = 500_000
    for year in range(0, 11):
        values = {}
        for strategy in strategies:
            net_return = max(-0.95, (strategy.annual_return_pct - strategy.expense_ratio_pct) / 100.0)
            values[strategy.name] = round(initial_amount * ((1 + net_return) ** year), 2)
        projected_growth.append(BenchmarkGrowthPointModel(year=year, values=values))

    notes = [
        f"Benchmark metrics were computed from ingested market data through {as_of_date.isoformat()}.",
        "Index and factor proxies use the same internal return-series engine so comparisons stay on a consistent footing.",
    ]
    return BenchmarkSummaryResponse(strategies=strategies, projected_growth=projected_growth, notes=notes)


def load_snapshots(
    db: Session,
    *,
    as_of_date: date | None = None,
    symbols: list[str] | None = None,
    lookback_days: int = 400,
    min_history: int = 40,
) -> list[Snapshot]:
    effective_date = as_of_date or get_effective_trade_date(db)
    start_date = effective_date - timedelta(days=lookback_days)
    stmt = (
        select(
            Instrument.symbol,
            Instrument.name,
            Instrument.sector,
            Instrument.instrument_type,
            Instrument.market_cap_bucket,
            DailyBar.trade_date,
            DailyBar.close_price,
            DailyBar.total_traded_value,
        )
        .join(DailyBar, DailyBar.instrument_id == Instrument.id)
        .where(DailyBar.trade_date >= start_date, DailyBar.trade_date <= effective_date)
        .order_by(Instrument.symbol, DailyBar.trade_date)
    )
    if symbols:
        stmt = stmt.where(Instrument.symbol.in_(symbols))

    rows = db.execute(stmt).all()
    grouped: dict[str, dict] = {}
    for row in rows:
        bucket = grouped.setdefault(
            row.symbol,
            {
                "name": row.name or row.symbol,
                "sector": row.sector or "Unknown",
                "instrument_type": row.instrument_type or ("ETF" if row.symbol.endswith("BEES") else "EQUITY"),
                "market_cap_bucket": row.market_cap_bucket,
                "closes": [],
                "turnover": [],
            },
        )
        bucket["closes"].append((row.trade_date, float(row.close_price)))
        bucket["turnover"].append(float(row.total_traded_value or 0))

    snapshots: list[Snapshot] = []
    for symbol, bucket in grouped.items():
        if len(bucket["closes"]) < min_history:
            continue
        closes = bucket["closes"]
        returns = build_return_series(closes)
        if len(returns) < max(5, min_history - 1):
            continue
        snapshots.append(
            Snapshot(
                symbol=symbol,
                name=bucket["name"],
                sector=bucket["sector"],
                instrument_type=bucket["instrument_type"],
                market_cap_bucket=bucket["market_cap_bucket"],
                latest_trade_date=closes[-1][0],
                latest_price=closes[-1][1],
                closes=closes,
                returns=returns,
                annual_return_pct=annualize_return(closes),
                annual_volatility_pct=annualize_volatility([item[1] for item in returns]),
                momentum_pct=compute_momentum_pct(closes, window=63),
                avg_traded_value=sum(bucket["turnover"][-20:]) / max(len(bucket["turnover"][-20:]), 1),
            )
        )

    benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
    benchmark_map = {trade_date: value for trade_date, value in (benchmark.returns if benchmark else [])}
    benchmark_vol = benchmark.annual_volatility_pct if benchmark else median([snapshot.annual_volatility_pct for snapshot in snapshots]) if snapshots else 15.0
    for snapshot in snapshots:
        overlap = []
        if benchmark and snapshot.symbol != benchmark.symbol:
            for trade_date, value in snapshot.returns:
                if trade_date in benchmark_map:
                    overlap.append((value, benchmark_map[trade_date]))
        if len(overlap) >= 20:
            x = [row[0] for row in overlap]
            y = [row[1] for row in overlap]
            snapshot.beta_proxy = round(covariance(x, y) / max(variance(y), 1e-9), 2)
        else:
            snapshot.beta_proxy = round(snapshot.annual_volatility_pct / max(benchmark_vol, 1.0), 2)
    return snapshots


def get_effective_trade_date(db: Session, as_of_date: date | None = None) -> date:
    stmt = select(func.max(DailyBar.trade_date))
    if as_of_date is not None:
        stmt = stmt.where(DailyBar.trade_date <= as_of_date)
    trade_date = db.execute(stmt).scalar_one_or_none()
    if trade_date is None:
        raise ValueError("No daily market data is available yet. Ingest bhavcopy data first.")
    return trade_date


def select_portfolio_candidates(risk_mode: str, snapshots: list[Snapshot]) -> list[tuple[Snapshot, float]]:
    target_count = {"ULTRA_LOW": 7, "MODERATE": 10, "HIGH": 10}[risk_mode]
    preference_order = {symbol: index for index, symbol in enumerate(RISK_MODE_UNIVERSES[risk_mode])}
    scored = sorted(
        snapshots,
        key=lambda snapshot: candidate_score(snapshot, risk_mode, preference_order.get(snapshot.symbol, 999)),
        reverse=True,
    )
    selected: list[Snapshot] = []
    seen_sectors: set[str] = set()
    for snapshot in scored:
        if snapshot.sector not in seen_sectors or len(selected) >= max(3, target_count // 2):
            selected.append(snapshot)
            seen_sectors.add(snapshot.sector)
        if len(selected) >= target_count:
            break
    if len(selected) < min(4, target_count):
        return []

    raw_weights = []
    for snapshot in selected:
        inv_vol = 1 / max(snapshot.annual_volatility_pct, 3.0)
        if risk_mode == "ULTRA_LOW":
            factor = inv_vol * (1.25 if snapshot.instrument_type == "ETF" else 1.0)
        elif risk_mode == "MODERATE":
            factor = inv_vol * max(0.5, 1 + (snapshot.annual_return_pct / 100.0))
        else:
            factor = max(0.25, 0.6 + (snapshot.momentum_pct / 100.0) + (snapshot.beta_proxy / 4.0))
        raw_weights.append(factor)
    weights = normalize_weights(raw_weights, max_weight={"ULTRA_LOW": 35.0, "MODERATE": 14.0, "HIGH": 12.0}[risk_mode])
    return list(zip(selected, weights))


def build_weighted_statistics(selected: list[tuple[Snapshot, float]]) -> PortfolioMetricsModel:
    weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in selected}
    snapshot_map = {snapshot.symbol: snapshot for snapshot, _ in selected}
    metrics = summarize_return_series(aggregate_portfolio_returns(snapshot_map, weights))
    weighted_beta = sum(snapshot.beta_proxy * weight for snapshot, weight in selected) / 100.0
    diversification_score = max(30.0, min(95.0, len({snapshot.sector for snapshot, _ in selected}) * 8 + (1 - average_pairwise_correlation([snapshot for snapshot, _ in selected])) * 40))
    return PortfolioMetricsModel(
        estimated_return_pct=round(metrics["annual_return_pct"], 2),
        estimated_volatility_pct=round(metrics["volatility_pct"], 2),
        beta=round(weighted_beta, 2),
        diversification_score=round(diversification_score, 1),
    )


def build_rationale(snapshot: Snapshot, risk_mode: str) -> str:
    if risk_mode == "ULTRA_LOW":
        return f"{snapshot.sector} sleeve with {snapshot.annual_volatility_pct:.1f}% annualized volatility and reliable liquidity."
    if risk_mode == "HIGH":
        return f"{snapshot.sector} growth candidate with {snapshot.momentum_pct:.1f}% recent momentum and beta proxy {snapshot.beta_proxy:.2f}."
    return f"Balanced exposure in {snapshot.sector}; annual return {snapshot.annual_return_pct:.1f}% with volatility {snapshot.annual_volatility_pct:.1f}%."


def build_rebalance_actions(priced_holdings, sector_weights, target_sectors, target_risk_mode: str, db: Session) -> list[RebalanceActionModel]:
    actions: list[RebalanceActionModel] = []
    largest_by_sector = {}
    for holding, snapshot, value in priced_holdings:
        current = largest_by_sector.get(snapshot.sector)
        if current is None or value > current[2]:
            largest_by_sector[snapshot.sector] = (holding, snapshot, value)

    for sector, current_weight in sorted(sector_weights.items(), key=lambda item: item[1], reverse=True):
        target_weight = target_sectors.get(sector, 0.0)
        if current_weight > target_weight + 5:
            _, snapshot, _ = largest_by_sector[sector]
            actions.append(
                RebalanceActionModel(
                    symbol=snapshot.symbol,
                    action="SELL",
                    target_weight=round(target_weight, 2),
                    current_weight=round(current_weight, 2),
                    reason=f"{sector} is above the target budget for {target_risk_mode.lower()} mode.",
                )
            )

    snapshots = load_snapshots(db, symbols=RISK_MODE_UNIVERSES[target_risk_mode], min_history=20)
    by_sector = defaultdict(list)
    for snapshot in snapshots:
        by_sector[snapshot.sector].append(snapshot)
    for sector, target_weight in sorted(target_sectors.items(), key=lambda item: item[1], reverse=True):
        current_weight = sector_weights.get(sector, 0.0)
        if current_weight + 5 < target_weight and by_sector.get(sector):
            candidate = sorted(by_sector[sector], key=lambda snapshot: snapshot.momentum_pct, reverse=True)[0]
            actions.append(
                RebalanceActionModel(
                    symbol=candidate.symbol,
                    action="BUY",
                    target_weight=round(target_weight, 2),
                    current_weight=round(current_weight, 2),
                    reason=f"{sector} is underweight versus the target allocation for {target_risk_mode.lower()} mode.",
                )
            )
        if len(actions) >= 6:
            break
    return actions[:6]


def load_close_matrix(db: Session, symbols: list[str], start_date: date, end_date: date) -> dict[str, dict[date, float]]:
    rows = db.execute(
        select(Instrument.symbol, DailyBar.trade_date, DailyBar.close_price)
        .join(DailyBar, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol.in_(symbols), DailyBar.trade_date >= start_date, DailyBar.trade_date <= end_date)
        .order_by(Instrument.symbol, DailyBar.trade_date)
    ).all()
    matrix: dict[str, dict[date, float]] = defaultdict(dict)
    for row in rows:
        matrix[row.symbol][row.trade_date] = float(row.close_price)
    return matrix


def initialize_positions(price_map, weights, first_date, initial_investment):
    cash_pool = [initial_investment]
    positions = {}
    for symbol, weight in weights.items():
        first_price = price_map.get(symbol, {}).get(first_date)
        if first_price is None:
            continue
        allocation_value = initial_investment * weight
        shares = int(allocation_value // first_price)
        cost_basis = shares * first_price
        cash_pool[0] -= cost_basis
        positions[symbol] = {
            "shares": shares,
            "entry_price": first_price,
            "entry_date": first_date,
            "cost_basis": cost_basis,
            "cash_pool": cash_pool,
        }
    return positions


def rebalance_positions(position_state, price_map, weights, trade_date, portfolio_value, costs, taxes) -> int:
    trades = 0
    if not position_state:
        return 0
    cash_pool = next(iter(position_state.values()))["cash_pool"]
    for symbol, state in position_state.items():
        price = price_map[symbol].get(trade_date)
        if price is None:
            continue
        target_value = portfolio_value * weights[symbol]
        current_value = state["shares"] * price
        difference = target_value - current_value
        if abs(difference) / max(portfolio_value, 1) < 0.03:
            continue
        if difference < 0 and state["shares"] > 0:
            sell_value = min(abs(difference), current_value)
            shares_to_sell = int(sell_value // price)
            if shares_to_sell <= 0:
                continue
            proceeds = shares_to_sell * price
            trade_costs = calculate_trade_costs(proceeds, is_buy=False)
            apply_costs(costs, trade_costs)
            average_cost = state["cost_basis"] / max(state["shares"], 1)
            gain = proceeds - (average_cost * shares_to_sell)
            holding_days = (trade_date - state["entry_date"]).days
            if holding_days < 365:
                taxes["stcg_gain"] += gain
            else:
                taxes["ltcg_gain"] += gain
            state["shares"] -= shares_to_sell
            state["cost_basis"] -= average_cost * shares_to_sell
            cash_pool[0] += proceeds - trade_costs["total_costs"]
            trades += 1
        elif difference > 0:
            spend = min(difference, cash_pool[0])
            shares_to_buy = int(spend // price)
            if shares_to_buy <= 0:
                continue
            trade_value = shares_to_buy * price
            trade_costs = calculate_trade_costs(trade_value, is_buy=True)
            total_outflow = trade_value + trade_costs["total_costs"]
            if total_outflow > cash_pool[0]:
                continue
            apply_costs(costs, trade_costs)
            cash_pool[0] -= total_outflow
            state["shares"] += shares_to_buy
            state["cost_basis"] += trade_value
            state["entry_price"] = price
            state["entry_date"] = trade_date
            trades += 1
    return trades


def build_backtest_metrics(equity_curve, portfolio_returns, costs, taxes, total_trades) -> BacktestMetricModel:
    initial_value = equity_curve[0].portfolio_value
    final_value = equity_curve[-1].portfolio_value
    years = max((equity_curve[-1].date - equity_curve[0].date).days / 365.25, 1 / 12)
    total_return_pct = ((final_value / max(initial_value, 1)) - 1) * 100
    cagr_pct = ((final_value / max(initial_value, 1)) ** (1 / years) - 1) * 100
    max_drawdown_pct = compute_max_drawdown([point.portfolio_value for point in equity_curve]) * 100
    avg_daily = sum(portfolio_returns) / max(len(portfolio_returns), 1)
    vol_daily = sqrt(sum((value - avg_daily) ** 2 for value in portfolio_returns) / max(len(portfolio_returns) - 1, 1)) if portfolio_returns else 0.0
    downside = [value for value in portfolio_returns if value < 0]
    downside_vol = sqrt(sum(value * value for value in downside) / max(len(downside), 1)) if downside else vol_daily
    sharpe_ratio = ((avg_daily - (RISK_FREE_RATE / 252)) / max(vol_daily, 1e-9)) * sqrt(252) if vol_daily else 0.0
    sortino_ratio = ((avg_daily - (RISK_FREE_RATE / 252)) / max(downside_vol, 1e-9)) * sqrt(252) if downside_vol else 0.0
    calmar_ratio = cagr_pct / max(max_drawdown_pct, 0.01)
    win_rate_pct = (sum(1 for value in portfolio_returns if value > 0) / max(len(portfolio_returns), 1)) * 100
    tax_drag_pct = (taxes["total_tax"] / max(initial_value, 1)) * 100
    cost_drag_pct = (costs["total_costs"] / max(initial_value, 1)) * 100
    return BacktestMetricModel(
        cagr_pct=round(cagr_pct, 2),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        sortino_ratio=round(sortino_ratio, 2),
        calmar_ratio=round(calmar_ratio, 2),
        turnover_pct=round(min(250.0, total_trades * 6.5), 2),
        win_rate_pct=round(win_rate_pct, 2),
        total_trades=total_trades,
        tax_drag_pct=round(tax_drag_pct, 2),
        cost_drag_pct=round(cost_drag_pct, 2),
        final_value=round(final_value, 2),
        initial_investment=round(initial_value, 2),
    )


def select_benchmark_symbol(db: Session) -> str:
    symbols = set(db.execute(select(Instrument.symbol).where(Instrument.symbol.in_(["NIFTYBEES", "LIQUIDBEES", "GOLDBEES"]))).scalars().all())
    if "NIFTYBEES" in symbols:
        return "NIFTYBEES"
    if "LIQUIDBEES" in symbols:
        return "LIQUIDBEES"
    if "GOLDBEES" in symbols:
        return "GOLDBEES"
    return next(iter(symbols), "NIFTYBEES")


def candidate_score(snapshot: Snapshot, risk_mode: str, preference_rank: int) -> float:
    preference_bonus = max(0.0, 12.0 - preference_rank)
    liquidity_bonus = min(snapshot.avg_traded_value / 50_000_000.0, 10.0)
    if risk_mode == "ULTRA_LOW":
        return (
            120.0 / max(snapshot.annual_volatility_pct, 4.0)
            + max(0.0, 20.0 - abs(snapshot.beta_proxy - 0.6) * 15.0)
            + (8.0 if snapshot.instrument_type == "ETF" else 0.0)
            + preference_bonus
            + liquidity_bonus
        )
    if risk_mode == "HIGH":
        return snapshot.annual_return_pct * 0.7 + snapshot.momentum_pct * 0.8 + snapshot.beta_proxy * 8.0 - snapshot.annual_volatility_pct * 0.12 + preference_bonus + liquidity_bonus
    return snapshot.annual_return_pct * 0.55 - snapshot.annual_volatility_pct * 0.18 + snapshot.momentum_pct * 0.25 + preference_bonus + liquidity_bonus


def normalize_weights(raw_weights: list[float], max_weight: float) -> list[float]:
    weights = [max(0.01, weight) for weight in raw_weights]
    total = sum(weights)
    normalized = [(weight / total) * 100 for weight in weights]
    changed = True
    while changed:
        changed = False
        excess = 0.0
        uncapped = []
        for index, weight in enumerate(normalized):
            if weight > max_weight:
                excess += weight - max_weight
                normalized[index] = max_weight
                changed = True
            else:
                uncapped.append(index)
        if changed and uncapped:
            uncapped_total = sum(normalized[index] for index in uncapped)
            for index in uncapped:
                normalized[index] += excess * (normalized[index] / max(uncapped_total, 1e-9))
    total = sum(normalized)
    return [round((weight / total) * 100, 2) for weight in normalized]


def build_return_series(closes: list[tuple[date, float]]) -> list[tuple[date, float]]:
    series = []
    for index in range(1, len(closes)):
        previous = closes[index - 1][1]
        current = closes[index][1]
        if previous <= 0:
            continue
        series.append((closes[index][0], (current / previous) - 1))
    return series


def aggregate_portfolio_returns(snapshot_map: dict[str, Snapshot], weights: dict[str, float]) -> dict[date, float]:
    combined: dict[date, float] = defaultdict(float)
    totals: dict[date, float] = defaultdict(float)
    for symbol, weight in weights.items():
        snapshot = snapshot_map.get(symbol)
        if snapshot is None:
            continue
        for trade_date, value in snapshot.returns:
            combined[trade_date] += value * weight
            totals[trade_date] += weight
    return {trade_date: combined[trade_date] / max(totals[trade_date], 1e-9) for trade_date in sorted(combined)}


def summarize_return_series(return_series: dict[date, float]) -> dict[str, float]:
    values = [return_series[trade_date] for trade_date in sorted(return_series)]
    if not values:
        return {"annual_return_pct": 0.0, "volatility_pct": 0.0, "sharpe_ratio": 0.0, "sortino_ratio": 0.0, "max_drawdown_pct": 0.0, "cagr_pct": 0.0}
    avg_daily = sum(values) / len(values)
    vol_daily = sqrt(sum((value - avg_daily) ** 2 for value in values) / max(len(values) - 1, 1)) if len(values) > 1 else 0.0
    downside = [value for value in values if value < 0]
    downside_vol = sqrt(sum(value * value for value in downside) / max(len(downside), 1)) if downside else vol_daily
    annual_return_pct = avg_daily * 252 * 100
    volatility_pct = vol_daily * sqrt(252) * 100
    sharpe_ratio = ((avg_daily - (RISK_FREE_RATE / 252)) / max(vol_daily, 1e-9)) * sqrt(252) if vol_daily else 0.0
    sortino_ratio = ((avg_daily - (RISK_FREE_RATE / 252)) / max(downside_vol, 1e-9)) * sqrt(252) if downside_vol else 0.0
    equity = []
    running = 1.0
    for value in values:
        running *= 1 + value
        equity.append(running)
    years = max(len(values) / 252, 1 / 12)
    cagr_pct = ((equity[-1] ** (1 / years)) - 1) * 100
    max_drawdown_pct = compute_max_drawdown(equity) * 100
    return {
        "annual_return_pct": round(annual_return_pct, 2),
        "volatility_pct": round(volatility_pct, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "sortino_ratio": round(sortino_ratio, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "cagr_pct": round(cagr_pct, 2),
    }


def annualize_return(closes: list[tuple[date, float]]) -> float:
    if len(closes) < 2 or closes[0][1] <= 0:
        return 0.0
    periods = max(len(closes) - 1, 1)
    return (((closes[-1][1] / closes[0][1]) ** (252 / periods)) - 1) * 100


def annualize_volatility(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    variance_value = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return sqrt(variance_value) * sqrt(252) * 100


def compute_momentum_pct(closes: list[tuple[date, float]], window: int) -> float:
    if len(closes) <= window:
        return ((closes[-1][1] / closes[0][1]) - 1) * 100
    return ((closes[-1][1] / closes[-window][1]) - 1) * 100


def average_pairwise_correlation(snapshots: list[Snapshot]) -> float:
    if len(snapshots) < 2:
        return 0.0
    pair_values = []
    for left_index in range(len(snapshots)):
        left_map = {trade_date: value for trade_date, value in snapshots[left_index].returns}
        for right_index in range(left_index + 1, len(snapshots)):
            overlap_left = []
            overlap_right = []
            for trade_date, value in snapshots[right_index].returns:
                if trade_date in left_map:
                    overlap_left.append(left_map[trade_date])
                    overlap_right.append(value)
            if len(overlap_left) >= 10:
                pair_values.append(correlation(overlap_left, overlap_right))
    return sum(pair_values) / len(pair_values) if pair_values else 0.0


def covariance(x: list[float], y: list[float]) -> float:
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    return sum((left - mean_x) * (right - mean_y) for left, right in zip(x, y)) / max(len(x) - 1, 1)


def variance(x: list[float]) -> float:
    mean = sum(x) / len(x)
    return sum((value - mean) ** 2 for value in x) / max(len(x) - 1, 1)


def correlation(x: list[float], y: list[float]) -> float:
    std_x = sqrt(variance(x))
    std_y = sqrt(variance(y))
    if std_x == 0 or std_y == 0:
        return 0.0
    return covariance(x, y) / (std_x * std_y)


def compute_max_drawdown(values: list[float]) -> float:
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / max(peak, 1e-9))
    return max_drawdown


def calculate_trade_costs(amount: float, *, is_buy: bool) -> dict[str, float]:
    brokerage = min(amount * BROKERAGE_RATE, MAX_BROKERAGE)
    stt = amount * (STT_BUY_RATE if is_buy else STT_SELL_RATE)
    stamp_duty = amount * STAMP_DUTY_RATE if is_buy else 0.0
    gst = brokerage * GST_RATE
    slippage = amount * SLIPPAGE_RATE
    total_costs = brokerage + stt + stamp_duty + gst + slippage
    return {
        "total_brokerage": brokerage,
        "total_stt": stt,
        "total_stamp_duty": stamp_duty,
        "total_gst": gst,
        "total_slippage": slippage,
        "total_costs": total_costs,
    }


def apply_costs(cost_bucket: dict[str, float], trade_costs: dict[str, float]) -> None:
    for key, value in trade_costs.items():
        cost_bucket[key] += value


def round_mapping(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}


def build_named_weights(snapshot_map: dict[str, Snapshot], symbols: list[str]) -> dict[str, float]:
    available = [symbol for symbol in symbols if symbol in snapshot_map]
    if not available:
        return build_equal_weight_portfolio(list(snapshot_map.values()), 8)
    weight = 1 / len(available)
    return {symbol: weight for symbol in available}


def build_equal_weight_portfolio(snapshots: list[Snapshot], count: int) -> dict[str, float]:
    ranked = sorted(snapshots, key=lambda snapshot: snapshot.avg_traded_value, reverse=True)[:count]
    if not ranked:
        return {}
    weight = 1 / len(ranked)
    return {snapshot.symbol: weight for snapshot in ranked}


def build_ranked_portfolio(snapshots: list[Snapshot], key, descending: bool, count: int) -> dict[str, float]:
    ranked = sorted(snapshots, key=key, reverse=descending)[:count]
    if not ranked:
        return {}
    weight = 1 / len(ranked)
    return {snapshot.symbol: weight for snapshot in ranked}
