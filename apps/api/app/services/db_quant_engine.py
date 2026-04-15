from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
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
    ModelVariant,
    TaxBreakdownModel,
)
from app.services.corporate_actions import (
    adjust_close_series,
    build_cumulative_factor_lookup,
    build_total_return_series,
    load_corporate_actions,
)
from app.services.market_rules import (
    financial_year_for_trade_date,
    resolve_capital_gains_tax_schedule,
    resolve_equity_fee_schedule,
)
from app.services.model_runtime import get_model_runtime_status

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
    ("NSE AI Portfolio", "AI", "Constrained covariance allocator using factor-aware expected returns."),
    ("Nifty 50 Proxy", "INDEX", "Large-cap, liquidity-weighted proxy for the top end of the NSE cash market."),
    ("Nifty 500 Proxy", "INDEX", "Broad-market proxy with large/mid/small bucket balancing across the ingested universe."),
    ("Momentum Factor", "FACTOR", "High-momentum proxy basket using 1M/3M/6M blended trend strength."),
    ("Quality Factor", "FACTOR", "Stability and downside-control proxy using lower drawdown and downside volatility."),
    ("AMC Multi Factor", "AMC_STYLE", "Diversified multi-factor sleeve blending momentum, quality, low volatility, and liquidity."),
]

BENCHMARK_METADATA = {
    "NSE AI Portfolio": {
        "construction_method": "Constrained long-only optimizer over local NSE snapshots using shrinkage covariance and model-aware expected returns.",
        "is_proxy": False,
        "constituent_method": "Local universe shortlist plus risk-mode allocator on ingested securities.",
        "limitations": [
            "Not a public index; this is the application strategy itself.",
            "Performance is based on the locally ingested research universe and cost assumptions.",
        ],
    },
    "Nifty 50 Proxy": {
        "construction_method": "Large-cap liquidity-weighted proxy reconstructed from the ingested local NSE universe.",
        "is_proxy": True,
        "constituent_method": "Point-in-time top-cap and liquidity screen; not official historical Nifty 50 constituent reconstitution.",
        "limitations": [
            "Official Nifty constituent history is not yet loaded locally.",
            "This series is a proxy and should not be read as the exact published index return.",
        ],
    },
    "Nifty 500 Proxy": {
        "construction_method": "Broad-market proxy with large, mid, and small-cap bucket balancing across ingested symbols.",
        "is_proxy": True,
        "constituent_method": "Bucket-balanced proxy over locally available EQ securities instead of official index constituents.",
        "limitations": [
            "Static proxy construction over the local universe, not a full official index rebuild.",
            "Coverage depends on locally ingested bhavcopy history and instrument metadata quality.",
        ],
    },
    "Momentum Factor": {
        "construction_method": "Top-ranked factor sleeve using local momentum scores and sector caps.",
        "is_proxy": True,
        "constituent_method": "Point-in-time factor ranking over the research universe with sector balancing.",
        "limitations": [
            "This is a research proxy, not an official NSE factor index.",
            "Weights are recomputed from local factor scores rather than external benchmark files.",
        ],
    },
    "Quality Factor": {
        "construction_method": "Quality-tilted proxy using drawdown, downside-volatility, and stability features.",
        "is_proxy": True,
        "constituent_method": "Point-in-time quality ranking over the local universe with sector balancing.",
        "limitations": [
            "This is a research proxy, not an official published quality index.",
            "Inputs are price/volume derived and do not include full fundamentals.",
        ],
    },
    "AMC Multi Factor": {
        "construction_method": "AMC-style blended multi-factor sleeve over the local research universe.",
        "is_proxy": True,
        "constituent_method": "Locally defined mix of momentum, quality, low-vol, and liquidity scores.",
        "limitations": [
            "This is a local style proxy and not a specific AMC scheme NAV series.",
            "Official fund holdings and expense-ratio drift are not yet part of the benchmark pipeline.",
        ],
    },
}

RISK_MODEL_CONFIG = {
    "ULTRA_LOW": {"candidate_count": 10, "max_weight": 0.35, "sector_cap": 0.42, "risk_aversion": 18.0, "shrinkage": 0.55, "turnover_penalty": 0.10, "drift_threshold": 0.06, "min_trade_weight": 0.03, "cooldown_days": 5},
    "MODERATE": {"candidate_count": 12, "max_weight": 0.16, "sector_cap": 0.28, "risk_aversion": 8.5, "shrinkage": 0.40, "turnover_penalty": 0.06, "drift_threshold": 0.04, "min_trade_weight": 0.025, "cooldown_days": 7},
    "HIGH": {"candidate_count": 12, "max_weight": 0.12, "sector_cap": 0.24, "risk_aversion": 4.25, "shrinkage": 0.30, "turnover_penalty": 0.04, "drift_threshold": 0.03, "min_trade_weight": 0.02, "cooldown_days": 10},
}

FACTOR_KEYS = ["momentum", "quality", "low_vol", "liquidity", "sector_strength", "size", "beta"]


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
    adjusted_closes: list[tuple[date, float]]
    # Adjusted OHLC series (split/bonus corrected via corporate actions).
    adjusted_opens: list[tuple[date, float]]
    adjusted_highs: list[tuple[date, float]]
    adjusted_lows: list[tuple[date, float]]
    returns: list[tuple[date, float]]
    annual_return_pct: float
    annual_volatility_pct: float
    momentum_1m_pct: float
    momentum_3m_pct: float
    momentum_6m_pct: float
    downside_volatility_pct: float
    max_drawdown_pct: float
    avg_traded_value: float
    corporate_action_count: int = 0
    beta_proxy: float = 1.0
    factor_scores: dict[str, float] = field(default_factory=dict)
    # LightGBM hybrid annotations (populated only when model_variant requests it).
    ml_pred_21d_return: float | None = None
    ml_pred_annual_return: float | None = None
    top_model_drivers: list[str] = field(default_factory=list)
    expected_return_source: str = "RULES"
    model_version: str = "rules"
    prediction_horizon_days: int = 21


@dataclass(frozen=True)
class BarRecord:
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    total_traded_value: float


def generate_portfolio(db: Session, payload: GeneratePortfolioRequest) -> GeneratePortfolioResponse:
    as_of_date = payload.as_of_date or get_effective_trade_date(db)
    runtime_status = get_model_runtime_status()
    model_variant_applied: ModelVariant = payload.model_variant
    if model_variant_applied == "LIGHTGBM_HYBRID" and not runtime_status.get("available"):
        model_variant_applied = "RULES"

    ml_min_history = 252 if model_variant_applied == "LIGHTGBM_HYBRID" else 126
    snapshots = load_snapshots(
        db,
        as_of_date=as_of_date,
        symbols=RISK_MODE_UNIVERSES[payload.risk_mode],
        min_history=ml_min_history,
    )
    if len(snapshots) < 4:
        snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=90)
    selected = select_portfolio_candidates(db, as_of_date, payload.risk_mode, snapshots, model_variant=model_variant_applied)
    if not selected:
        raise ValueError("Not enough historical market data to generate a portfolio. Ingest bhavcopy data first.")

    weighted_stats = build_weighted_statistics(selected)
    factor_exposures = compute_factor_exposures([(snapshot, weight / 100.0) for snapshot, weight in selected])
    adjusted_names = sum(1 for snapshot, _ in selected if snapshot.corporate_action_count > 0)
    notes = [
        f"Portfolio built from {len(selected)} instruments using prices through {as_of_date.isoformat()}.",
        "Expected returns blend 1M/3M/6M momentum, downside-aware quality, low-volatility preference, liquidity, sector strength, and beta discipline.",
        "Weights are produced by a constrained allocator over a shrinkage covariance matrix estimated from aligned total-return series.",
        f"Weighted factor exposures: momentum {factor_exposures['momentum']:+.2f}, quality {factor_exposures['quality']:+.2f}, low_vol {factor_exposures['low_vol']:+.2f}.",
        (
            f"Corporate-action-adjusted histories were used for {adjusted_names} selected instruments."
            if adjusted_names
            else "No corporate actions were loaded for the selected instruments, so adjusted and raw close histories currently match."
        ),
    ]

    used_ml_count = sum(1 for snapshot, _ in selected if snapshot.expected_return_source != "RULES")
    model_source = "ENSEMBLE" if used_ml_count > 0 else "RULES"
    model_version = next((snapshot.model_version for snapshot, _ in selected if snapshot.expected_return_source != "RULES"), "rules")
    prediction_horizon_days = next((snapshot.prediction_horizon_days for snapshot, _ in selected if snapshot.expected_return_source != "RULES"), 21)
    active_mode = runtime_status.get("active_mode", "rules_only") if used_ml_count > 0 else "rules_only"
    artifact_classification = str(runtime_status.get("artifact_classification", "missing")) if used_ml_count > 0 else "missing"

    if payload.model_variant == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            notes.append(
                f"Ensemble runtime used for {used_ml_count} equities in {active_mode.replace('_', ' ')} mode; blended predicted annual return with rule expected returns (75/25). Model version: {model_version}."
            )
        else:
            notes.append(
                f"Ensemble runtime requested, but no valid ML predictions were produced; using rule expected returns for all instruments. Status: {runtime_status.get('reason', 'rules_fallback')}."
            )

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
                top_model_drivers=list(snapshot.top_model_drivers),
            )
        )

    db.commit()
    return GeneratePortfolioResponse(
        model_variant=model_variant_applied,
        model_source=model_source,  # type: ignore[arg-type]
        model_version=model_version,
        prediction_horizon_days=prediction_horizon_days,
        active_mode=active_mode,
        artifact_classification=artifact_classification,
        risk_mode=payload.risk_mode,
        investment_amount=payload.investment_amount,
        allocations=allocations,
        metrics=weighted_stats,
        notes=notes,
    )


def analyze_portfolio(db: Session, payload: AnalyzePortfolioRequest) -> AnalyzePortfolioResponse:
    runtime_status = get_model_runtime_status()
    if payload.model_variant is None:
        model_variant_applied: ModelVariant = "LIGHTGBM_HYBRID" if runtime_status.get("available") else "RULES"
    else:
        model_variant_applied = payload.model_variant
        if model_variant_applied == "LIGHTGBM_HYBRID" and not runtime_status.get("available"):
            model_variant_applied = "RULES"

    ml_min_history = 252 if model_variant_applied == "LIGHTGBM_HYBRID" else 63
    snapshots = load_snapshots(db, symbols=[holding.symbol for holding in payload.holdings], min_history=ml_min_history)
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

    factor_exposures = compute_factor_exposures([(snapshot, value / total_value) for _, snapshot, value in priced_holdings])
    as_of_date = get_effective_trade_date(db)
    target_min_history = 252 if model_variant_applied == "LIGHTGBM_HYBRID" else 126
    target_snapshots = load_snapshots(
        db,
        as_of_date=as_of_date,
        symbols=RISK_MODE_UNIVERSES[payload.target_risk_mode],
        min_history=target_min_history,
    )
    if len(target_snapshots) < 4:
        target_snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=90)
    target_portfolio = select_portfolio_candidates(db, as_of_date, payload.target_risk_mode, target_snapshots, model_variant=model_variant_applied)
    actions = build_rebalance_actions(priced_holdings, total_value, target_portfolio, payload.target_risk_mode)
    rebalance_days = {"ULTRA_LOW": "quarterly", "MODERATE": "monthly review / quarterly hard rebalance", "HIGH": "monthly with tighter drift checks"}[payload.target_risk_mode]
    notes = [
        f"Analysis used latest close prices for {len(priced_holdings)} holdings from PostgreSQL.",
        f"Average pairwise trailing correlation across the priced holdings is {avg_corr:.2f}.",
        (
            f"Current factor exposures are momentum {factor_exposures['momentum']:+.2f}, quality {factor_exposures['quality']:+.2f}, "
            f"low_vol {factor_exposures['low_vol']:+.2f}, liquidity {factor_exposures['liquidity']:+.2f}."
        ),
        (
            f"Rebalance actions compare the live holdings against the current {payload.target_risk_mode.lower()} target portfolio "
            f"with a drift threshold of {RISK_MODEL_CONFIG[payload.target_risk_mode]['drift_threshold'] * 100:.1f}% and {rebalance_days} reviews."
        ),
    ]
    if missing_symbols:
        notes.append(f"No market data found yet for: {', '.join(sorted(set(missing_symbols)))}.")

    used_ml_count = sum(1 for snapshot, _ in target_portfolio if snapshot.expected_return_source != "RULES")

    model_source_note = ""
    if model_variant_applied == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            model_source_note = (
                f"Ensemble runtime applied to {used_ml_count} equities in {runtime_status.get('active_mode', 'degraded_ensemble').replace('_', ' ')} mode; "
                "allocator used blended ML+rules expected returns (75/25)."
            )
        else:
            model_source_note = f"Ensemble runtime requested, but no valid equity predictions were produced; using rules expected returns. Status: {runtime_status.get('reason', 'rules_fallback')}."
    if model_source_note:
        notes.append(model_source_note)

    ml_predictions: dict[str, float] = {}
    top_model_drivers_by_symbol: dict[str, list[str]] = {}
    if model_variant_applied == "LIGHTGBM_HYBRID" and snapshots:
        try:
            from app.ml.ensemble_alpha.predict import EnsembleAlphaPredictor

            predictor = EnsembleAlphaPredictor()
            pred_map, model_info = predictor.predict(db, snapshots, as_of_date)
            for sym, pred in pred_map.items():
                ml_predictions[sym] = pred.pred_annual_return
            for snapshot in snapshots:
                if snapshot.symbol in pred_map and snapshot.instrument_type == "EQUITY":
                    snapshot.expected_return_source = str(model_info.get("model_source", "ENSEMBLE"))
                    snapshot.top_model_drivers = list(pred_map[snapshot.symbol].top_drivers)
                    snapshot.ml_pred_annual_return = float(pred_map[snapshot.symbol].pred_annual_return)
                    snapshot.ml_pred_21d_return = float(pred_map[snapshot.symbol].pred_21d_return)
                    snapshot.model_version = str(model_info.get("model_version", "unknown"))
                    snapshot.prediction_horizon_days = int(model_info.get("prediction_horizon_days", 21))
                    top_model_drivers_by_symbol[snapshot.symbol] = list(snapshot.top_model_drivers)
        except Exception:
            # If prediction fails for the holdings, keep defaults (rules).
            pass

    return AnalyzePortfolioResponse(
        total_holdings=len(payload.holdings),
        portfolio_value=round(total_value, 2),
        current_beta=current_beta,
        diversification_score=diversification_score,
        sector_weights=sector_weights,
        factor_exposures={key: round(value, 2) for key, value in factor_exposures.items()},
        correlation_risk=correlation_risk,
        actions=actions,
        model_variant_applied=model_variant_applied,
        model_source="ENSEMBLE" if used_ml_count > 0 else "RULES",
        model_version=next((snapshot.model_version for snapshot in snapshots if snapshot.expected_return_source != "RULES"), runtime_status.get("model_version", "rules")),
        prediction_horizon_days=next((snapshot.prediction_horizon_days for snapshot in snapshots if snapshot.expected_return_source != "RULES"), int(runtime_status.get("prediction_horizon_days", 21))),
        active_mode=runtime_status.get("active_mode", "rules_only") if used_ml_count > 0 else "rules_only",
        artifact_classification=str(runtime_status.get("artifact_classification", "missing")) if used_ml_count > 0 else "missing",
        ml_predictions=ml_predictions,
        top_model_drivers_by_symbol=top_model_drivers_by_symbol,
        notes=notes,
    )


def run_backtest(db: Session, payload: BacktestRequest) -> BacktestResultResponse:
    runtime_status = get_model_runtime_status()
    model_variant_applied = payload.model_variant
    if model_variant_applied == "LIGHTGBM_HYBRID" and not runtime_status.get("available"):
        model_variant_applied = "RULES"

    selection_date = get_effective_trade_date(db, payload.start_date)
    ml_min_history = 252 if model_variant_applied == "LIGHTGBM_HYBRID" else 126
    snapshots = load_snapshots(
        db,
        as_of_date=selection_date,
        symbols=RISK_MODE_UNIVERSES[payload.risk_mode],
        min_history=ml_min_history,
    )
    if len(snapshots) < 4:
        snapshots = load_snapshots(db, as_of_date=selection_date, min_history=90)
    model_portfolio = select_portfolio_candidates(db, as_of_date, payload.risk_mode, snapshots, model_variant=model_variant_applied)
    if not model_portfolio:
        raise ValueError("Not enough historical market data to backtest. Ingest bhavcopy data first.")

    weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in model_portfolio}
    snapshot_by_symbol = {snapshot.symbol: snapshot for snapshot, _ in model_portfolio}
    bar_matrix, dividend_cash = load_bar_matrix(db, list(weights.keys()), payload.start_date, payload.end_date)
    benchmark_symbol = select_benchmark_symbol(db)
    benchmark_matrix, _ = load_bar_matrix(db, [benchmark_symbol], payload.start_date, payload.end_date)
    benchmark_series = benchmark_matrix.get(benchmark_symbol, {})
    benchmark_dates = sorted(benchmark_series)
    benchmark_first_price = benchmark_series[benchmark_dates[0]].close_price if benchmark_dates else None
    all_dates = sorted({trade_date for symbol_prices in bar_matrix.values() for trade_date in symbol_prices.keys()})
    if len(all_dates) < 2:
        raise ValueError("Backtest window does not have enough daily bars for the selected strategy.")

    costs = {
        "total_brokerage": 0.0,
        "total_stt": 0.0,
        "total_stamp_duty": 0.0,
        "total_exchange_txn": 0.0,
        "total_sebi_fees": 0.0,
        "total_gst": 0.0,
        "total_slippage": 0.0,
        "total_costs": 0.0,
    }
    taxes = {
        "stcg_gain": 0.0,
        "ltcg_gain": 0.0,
        "stcg_tax": 0.0,
        "ltcg_tax": 0.0,
        "cess_tax": 0.0,
        "total_tax": 0.0,
    }
    tax_buckets: dict[str, dict] = {
        "stcg": defaultdict(float),
        "ltcg_positive": defaultdict(float),
        "ltcg_negative": defaultdict(float),
    }
    position_state, initial_trades = initialize_positions(
        bar_matrix=bar_matrix,
        weights=weights,
        first_date=all_dates[0],
        initial_investment=DEFAULT_BACKTEST_INVESTMENT,
        costs=costs,
        snapshot_by_symbol=snapshot_by_symbol,
    )
    if not position_state:
        raise ValueError("Selected instruments do not have usable prices on the requested backtest start date.")
    equity_curve: list[CurvePointModel] = []
    portfolio_returns: list[float] = []
    prev_value = DEFAULT_BACKTEST_INVESTMENT
    total_trades = initial_trades

    rebalance_interval = {"MONTHLY": 21, "QUARTERLY": 63, "ANNUALLY": 252, "NONE": 10**9}[payload.rebalance_frequency]

    for index, trade_date in enumerate(all_dates):
        for symbol, state in position_state.items():
            cash_dividend = dividend_cash.get(symbol, {}).get(trade_date, 0.0)
            if cash_dividend > 0 and state["shares"] > 0:
                state["cash_pool"][0] += cash_dividend * state["shares"]

            bar = bar_matrix.get(symbol, {}).get(trade_date)
            if bar is None or state["shares"] <= 0:
                continue
            state["peak_price"] = max(state["peak_price"], bar.high_price)
            exit_fill, _ = determine_exit_fill(bar, state, payload.risk_mode, payload.stop_loss_pct, payload.take_profit_pct)
            if exit_fill is not None:
                proceeds = exit_fill * state["shares"]
                trade_costs = calculate_trade_costs(
                    amount=proceeds,
                    trade_date=trade_date,
                    is_buy=False,
                    avg_traded_value=state["avg_traded_value"],
                    annual_volatility_pct=state["annual_volatility_pct"],
                )
                apply_costs(costs, trade_costs)
                sold_shares = state["shares"]
                state["cash_pool"][0] += proceeds - trade_costs["total_costs"]
                realize_tax_lots(state, sold_shares, exit_fill, trade_date, taxes, tax_buckets)
                state["shares"] = 0
                state["peak_price"] = 0.0
                state["cooldown_until"] = trade_date + timedelta(days=RISK_MODEL_CONFIG[payload.risk_mode]["cooldown_days"])
                total_trades += 1

        portfolio_value = current_portfolio_value(position_state, bar_matrix, trade_date)

        if index > 0 and index % rebalance_interval == 0 and payload.rebalance_frequency != "NONE":
            total_trades += rebalance_positions(position_state, bar_matrix, weights, trade_date, portfolio_value, costs, taxes, tax_buckets, payload.risk_mode)
            portfolio_value = current_portfolio_value(position_state, bar_matrix, trade_date)

        if index > 0:
            portfolio_returns.append((portfolio_value - prev_value) / max(prev_value, 1))
        prev_value = portfolio_value

        benchmark_value = DEFAULT_BACKTEST_INVESTMENT
        if benchmark_first_price and trade_date in benchmark_series:
            benchmark_price = benchmark_series[trade_date].close_price
            benchmark_value = DEFAULT_BACKTEST_INVESTMENT * (benchmark_price / benchmark_first_price)

        equity_curve.append(
            CurvePointModel(
                date=trade_date,
                portfolio_value=round(portfolio_value, 2),
                benchmark_value=round(benchmark_value, 2),
            )
        )

    finalize_tax_buckets(taxes, tax_buckets)

    metrics = build_backtest_metrics(equity_curve, portfolio_returns, costs, taxes, total_trades)
    run_id = f"bt-{uuid4()}"
    fee_schedule = resolve_equity_fee_schedule(payload.end_date)
    tax_schedule = resolve_capital_gains_tax_schedule(payload.end_date)
    adjusted_names = sum(1 for snapshot in snapshot_by_symbol.values() if snapshot.corporate_action_count > 0)
    notes = [
        f"Historical replay used {len(weights)} data-backed instruments between {payload.start_date.isoformat()} and {payload.end_date.isoformat()}.",
        "Stop-loss and take-profit were evaluated on adjusted OHLC bars with gap-aware fills at the open when a threshold was crossed overnight.",
        (
            f"Rebalance policy used a {RISK_MODEL_CONFIG[payload.risk_mode]['drift_threshold'] * 100:.1f}% drift threshold and "
            f"{payload.rebalance_frequency.lower()} review cycle for {payload.risk_mode.lower()} mode."
        ),
        f"Equity fees used the {fee_schedule.effective_from.isoformat()} rule set: {fee_schedule.notes}",
        f"Capital gains used the {tax_schedule.effective_from.isoformat()} rule set with FY-wise LTCG exemption handling: {tax_schedule.notes}",
        (
            f"Corporate actions were applied to {adjusted_names} portfolio instruments, including split/bonus price adjustment and dividend cash credits."
            if adjusted_names
            else "No corporate actions were loaded for the portfolio instruments in this backtest window."
        ),
    ]

    used_ml_count = sum(1 for snapshot, _ in model_portfolio if snapshot.expected_return_source != "RULES")
    top_model_drivers_by_symbol = {
        snapshot.symbol: list(snapshot.top_model_drivers) for snapshot, _ in model_portfolio if snapshot.top_model_drivers
    }
    model_source = "ENSEMBLE" if used_ml_count > 0 else "RULES"
    model_version = next((snapshot.model_version for snapshot, _ in model_portfolio if snapshot.expected_return_source != "RULES"), "rules")
    prediction_horizon_days = next((snapshot.prediction_horizon_days for snapshot, _ in model_portfolio if snapshot.expected_return_source != "RULES"), 21)
    active_mode = runtime_status.get("active_mode", "rules_only") if used_ml_count > 0 else "rules_only"
    artifact_classification = str(runtime_status.get("artifact_classification", "missing")) if used_ml_count > 0 else "missing"
    if payload.model_variant == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            notes.append(
                f"Ensemble runtime used for {used_ml_count} equities in {active_mode.replace('_', ' ')} mode; blended predicted annual returns with rule expected returns (75/25). Model version: {model_version}."
            )
        else:
            notes.append(
                f"Ensemble runtime requested, but no valid equity predictions were produced; using rule expected returns for the portfolio. Status: {runtime_status.get('reason', 'rules_fallback')}."
            )

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
                "equity_curve": [point.model_dump(mode="json") for point in equity_curve],
                "notes": notes,
                "model_info": {
                    "model_variant": model_variant_applied,
                    "model_source": model_source,
                    "model_version": model_version,
                    "prediction_horizon_days": prediction_horizon_days,
                    "active_mode": active_mode,
                    "artifact_classification": artifact_classification,
                    "top_model_drivers_by_symbol": top_model_drivers_by_symbol,
                },
            },
            notes="\n".join(notes),
        )
    )
    db.commit()

    return BacktestResultResponse(
        model_variant=model_variant_applied,
        model_source=model_source,  # type: ignore[arg-type]
        model_version=model_version,
        prediction_horizon_days=prediction_horizon_days,
        active_mode=active_mode,
        artifact_classification=artifact_classification,
        top_model_drivers_by_symbol=top_model_drivers_by_symbol,
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
    model_info = payload.get("model_info", {}) if isinstance(payload, dict) else {}
    model_variant = model_info.get("model_variant", "RULES")
    model_source = model_info.get("model_source", "RULES")
    model_version = model_info.get("model_version", "rules")
    prediction_horizon_days = model_info.get("prediction_horizon_days", 21)
    active_mode = model_info.get("active_mode", "rules_only")
    artifact_classification = model_info.get("artifact_classification", "missing")
    top_model_drivers_by_symbol = model_info.get("top_model_drivers_by_symbol", {})
    return BacktestResultResponse(
        model_variant=model_variant,
        model_source=model_source,  # type: ignore[arg-type]
        model_version=model_version,
        prediction_horizon_days=prediction_horizon_days,
        active_mode=active_mode,
        artifact_classification=artifact_classification,
        top_model_drivers_by_symbol=top_model_drivers_by_symbol,
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
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=126)
    if not snapshots:
        raise ValueError("No benchmark data is available yet. Ingest bhavcopy data first.")
    source_window_start = min(
        (snapshot.adjusted_closes[0][0] if snapshot.adjusted_closes else snapshot.latest_trade_date)
        for snapshot in snapshots
    )

    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots}
    benchmark_portfolios = {
        "NSE AI Portfolio": dict((snapshot.symbol, weight / 100.0) for snapshot, weight in select_portfolio_candidates(db, as_of_date, "MODERATE", snapshots)),
        "Nifty 50 Proxy": build_nifty50_proxy_portfolio(snapshots),
        "Nifty 500 Proxy": build_nifty500_proxy_portfolio(snapshots),
        "Momentum Factor": build_factor_portfolio(snapshots, factor_key="momentum", count=12, sector_cap=0.25),
        "Quality Factor": build_factor_portfolio(snapshots, factor_key="quality", count=12, sector_cap=0.25),
        "AMC Multi Factor": build_multifactor_portfolio(snapshots, count=15, sector_cap=0.22),
    }

    strategies = []
    for name, category, description in BENCHMARK_UNIVERSES:
        metrics = summarize_return_series(aggregate_portfolio_returns(snapshot_map, benchmark_portfolios.get(name, {})))
        expense_ratio = 0.08 if category == "AI" else 0.06 if category == "INDEX" else 0.34
        benchmark_metadata = BENCHMARK_METADATA.get(name, {})
        strategies.append(
            BenchmarkMetricModel(
                name=name,
                description=description,
                category=category,  # type: ignore[arg-type]
                construction_method=benchmark_metadata.get("construction_method", "Local research benchmark over ingested NSE data."),
                is_proxy=bool(benchmark_metadata.get("is_proxy", True)),
                source_window=f"{source_window_start.isoformat()} to {as_of_date.isoformat()}",
                constituent_method=benchmark_metadata.get("constituent_method", "Local proxy construction"),
                limitations=list(benchmark_metadata.get("limitations", [])),
                annual_return_pct=metrics["annual_return_pct"],
                volatility_pct=metrics["volatility_pct"],
                sharpe_ratio=metrics["sharpe_ratio"],
                sortino_ratio=metrics["sortino_ratio"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                cagr_5y_pct=metrics["cagr_pct"],
                expense_ratio_pct=expense_ratio,
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
        "Index benchmarks are proxy constructions over the ingested NSE universe because official constituent files are not yet part of the local pipeline.",
        "Factor benchmarks use the same factor model as the allocator: momentum, quality proxy, low-volatility, liquidity, and sector balancing.",
        "Benchmark series are still static point-in-time proxy portfolios rather than fully materialized historical reconstitution jobs.",
    ]
    return BenchmarkSummaryResponse(strategies=strategies, projected_growth=projected_growth, notes=notes)


def load_snapshots(
    db: Session,
    *,
    as_of_date: date | None = None,
    symbols: list[str] | None = None,
    lookback_days: int = 450,
    min_history: int = 90,
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
            DailyBar.open_price,
            DailyBar.high_price,
            DailyBar.low_price,
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
                "opens": [],
                "highs": [],
                "lows": [],
                "turnover": [],
            },
        )
        bucket["closes"].append((row.trade_date, float(row.close_price)))
        bucket["opens"].append((row.trade_date, float(row.open_price)))
        bucket["highs"].append((row.trade_date, float(row.high_price)))
        bucket["lows"].append((row.trade_date, float(row.low_price)))
        bucket["turnover"].append(float(row.total_traded_value or 0))

    action_map = load_corporate_actions(db, symbols=list(grouped.keys()), end_date=effective_date) if grouped else {}
    snapshots: list[Snapshot] = []
    for symbol, bucket in grouped.items():
        if len(bucket["closes"]) < min_history:
            continue

        closes = bucket["closes"]
        actions = action_map.get(symbol, [])
        adjusted_closes, dividend_by_date = adjust_close_series(closes, actions)

        # Apply the same split/bonus correction factor to OHLC for ML feature engineering.
        factor_lookup = build_cumulative_factor_lookup(closes, actions)
        adjusted_opens = [(trade_date, price * factor_lookup.get(trade_date, 1.0)) for trade_date, price in bucket["opens"]]
        adjusted_highs = [(trade_date, price * factor_lookup.get(trade_date, 1.0)) for trade_date, price in bucket["highs"]]
        adjusted_lows = [(trade_date, price * factor_lookup.get(trade_date, 1.0)) for trade_date, price in bucket["lows"]]
        returns = build_total_return_series(adjusted_closes, dividend_by_date)
        if len(returns) < max(5, min_history - 1):
            continue

        adjusted_prices = [price for _, price in adjusted_closes]
        snapshots.append(
            Snapshot(
                symbol=symbol,
                name=bucket["name"],
                sector=bucket["sector"],
                instrument_type=bucket["instrument_type"],
                market_cap_bucket=bucket["market_cap_bucket"],
                latest_trade_date=adjusted_closes[-1][0],
                latest_price=adjusted_closes[-1][1],
                closes=closes,
                adjusted_closes=adjusted_closes,
                adjusted_opens=adjusted_opens,
                adjusted_highs=adjusted_highs,
                adjusted_lows=adjusted_lows,
                returns=returns,
                annual_return_pct=annualize_return(adjusted_closes),
                annual_volatility_pct=annualize_volatility([item[1] for item in returns]),
                momentum_1m_pct=compute_momentum_pct(adjusted_closes, window=21),
                momentum_3m_pct=compute_momentum_pct(adjusted_closes, window=63),
                momentum_6m_pct=compute_momentum_pct(adjusted_closes, window=126),
                downside_volatility_pct=annualize_volatility([item[1] for item in returns if item[1] < 0]),
                max_drawdown_pct=compute_max_drawdown(adjusted_prices) * 100,
                avg_traded_value=sum(bucket["turnover"][-20:]) / max(len(bucket["turnover"][-20:]), 1),
                corporate_action_count=len(action_map.get(symbol, [])),
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
    populate_factor_scores(snapshots)
    return snapshots


def get_effective_trade_date(db: Session, as_of_date: date | None = None) -> date:
    min_trade_date, max_trade_date = db.execute(select(func.min(DailyBar.trade_date), func.max(DailyBar.trade_date))).one()
    if max_trade_date is None:
        raise ValueError("No daily market data is available yet. Ingest bhavcopy data first.")

    if as_of_date is not None and min_trade_date is not None and as_of_date < min_trade_date:
        raise ValueError(
            f"Requested date {as_of_date.isoformat()} is earlier than the available market data range "
            f"({min_trade_date.isoformat()} to {max_trade_date.isoformat()})."
        )

    stmt = select(func.max(DailyBar.trade_date))
    if as_of_date is not None:
        stmt = stmt.where(DailyBar.trade_date <= as_of_date)
    trade_date = db.execute(stmt).scalar_one_or_none()
    if trade_date is None:
        raise ValueError(
            f"No daily market data is available on or before {as_of_date.isoformat() if as_of_date else 'the requested date'}. "
            f"Available range: {min_trade_date.isoformat()} to {max_trade_date.isoformat()}."
        )
    return trade_date


def select_portfolio_candidates(db, as_of_date,
    risk_mode: str,
    snapshots: list[Snapshot],
    model_variant: ModelVariant = "RULES",
) -> list[tuple[Snapshot, float]]:
    config = RISK_MODEL_CONFIG[risk_mode]
    screened = shortlist_candidates(risk_mode, snapshots, config["candidate_count"])
    if len(screened) < 4:
        return []

    aligned_snapshots, return_matrix = align_return_matrix(screened)
    if len(aligned_snapshots) < 4 or len(return_matrix[0]) < 20:
        return []

    expected_returns = estimate_expected_returns(db, as_of_date, aligned_snapshots, return_matrix, risk_mode, model_variant=model_variant)
    covariance_matrix = build_shrunk_covariance(return_matrix, config["shrinkage"])
    optimized_weights = optimize_constrained_allocator(
        aligned_snapshots,
        expected_returns,
        covariance_matrix,
        risk_mode,
    )
    if not optimized_weights:
        return []
    return list(zip(aligned_snapshots, [round(weight * 100, 2) for weight in optimized_weights]))


def build_weighted_statistics(selected: list[tuple[Snapshot, float]]) -> PortfolioMetricsModel:
    weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in selected}
    snapshot_map = {snapshot.symbol: snapshot for snapshot, _ in selected}
    metrics = summarize_return_series(aggregate_portfolio_returns(snapshot_map, weights))
    weighted_beta = sum(snapshot.beta_proxy * (weight / 100.0) for snapshot, weight in selected)
    diversification_score = max(
        30.0,
        min(95.0, len({snapshot.sector for snapshot, _ in selected}) * 8 + (1 - average_pairwise_correlation([snapshot for snapshot, _ in selected])) * 40),
    )
    return PortfolioMetricsModel(
        estimated_return_pct=round(metrics["annual_return_pct"], 2),
        estimated_volatility_pct=round(metrics["volatility_pct"], 2),
        beta=round(weighted_beta, 2),
        diversification_score=round(diversification_score, 1),
    )


def build_rationale(snapshot: Snapshot, risk_mode: str) -> str:
    if risk_mode == "ULTRA_LOW":
        return (
            f"{snapshot.sector} sleeve with low-vol {snapshot.factor_scores.get('low_vol', 0):+.2f}, "
            f"quality {snapshot.factor_scores.get('quality', 0):+.2f}, and reliable liquidity."
        )
    if risk_mode == "HIGH":
        return (
            f"{snapshot.sector} growth candidate with momentum {snapshot.factor_scores.get('momentum', 0):+.2f}, "
            f"sector strength {snapshot.factor_scores.get('sector_strength', 0):+.2f}, and beta proxy {snapshot.beta_proxy:.2f}."
        )
    return (
        f"Balanced exposure in {snapshot.sector}; momentum {snapshot.factor_scores.get('momentum', 0):+.2f}, "
        f"quality {snapshot.factor_scores.get('quality', 0):+.2f}, low_vol {snapshot.factor_scores.get('low_vol', 0):+.2f}."
    )


def build_rebalance_actions(priced_holdings, total_value: float, target_portfolio: list[tuple[Snapshot, float]], target_risk_mode: str) -> list[RebalanceActionModel]:
    if not target_portfolio:
        return []

    current_weights = {snapshot.symbol: (value / total_value) * 100 for _, snapshot, value in priced_holdings}
    target_weights = {snapshot.symbol: weight for snapshot, weight in target_portfolio}
    symbol_map = {snapshot.symbol: snapshot for _, snapshot, _ in priced_holdings}
    symbol_map.update({snapshot.symbol: snapshot for snapshot, _ in target_portfolio})
    threshold_pct = RISK_MODEL_CONFIG[target_risk_mode]["drift_threshold"] * 100

    ranked_actions: list[tuple[float, RebalanceActionModel]] = []
    for symbol in sorted(set(current_weights) | set(target_weights)):
        current_weight = current_weights.get(symbol, 0.0)
        target_weight = target_weights.get(symbol, 0.0)
        drift = target_weight - current_weight
        if abs(drift) < threshold_pct:
            continue
        snapshot = symbol_map.get(symbol)
        if snapshot is None:
            continue
        action = "BUY" if drift > 0 else "SELL"
        reason = (
            f"{snapshot.sector} exposure drifted by {abs(drift):.1f}%; target model favors momentum {snapshot.factor_scores.get('momentum', 0):+.2f} and quality {snapshot.factor_scores.get('quality', 0):+.2f}."
            if action == "BUY"
            else f"{snapshot.sector} exposure is above the current {target_risk_mode.lower()} target and exceeds the drift threshold."
        )
        ranked_actions.append(
            (
                abs(drift),
                RebalanceActionModel(
                    symbol=symbol,
                    action=action,
                    target_weight=round(target_weight, 2),
                    current_weight=round(current_weight, 2),
                    reason=reason,
                ),
            )
        )
    ranked_actions.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked_actions[:8]]


def load_bar_matrix(db: Session, symbols: list[str], start_date: date, end_date: date) -> tuple[dict[str, dict[date, BarRecord]], dict[str, dict[date, float]]]:
    rows = db.execute(
        select(
            Instrument.symbol,
            DailyBar.trade_date,
            DailyBar.open_price,
            DailyBar.high_price,
            DailyBar.low_price,
            DailyBar.close_price,
            DailyBar.total_traded_value,
        )
        .join(DailyBar, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol.in_(symbols), DailyBar.trade_date >= start_date, DailyBar.trade_date <= end_date)
        .order_by(Instrument.symbol, DailyBar.trade_date)
    ).all()
    grouped: dict[str, list[tuple[date, float, float, float, float, float]]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(
            (
                row.trade_date,
                float(row.open_price),
                float(row.high_price),
                float(row.low_price),
                float(row.close_price),
                float(row.total_traded_value or 0.0),
            )
        )

    action_map = load_corporate_actions(db, symbols=list(grouped.keys()), end_date=end_date) if grouped else {}
    matrix: dict[str, dict[date, BarRecord]] = defaultdict(dict)
    dividend_cash: dict[str, dict[date, float]] = defaultdict(dict)
    for symbol, bars in grouped.items():
        close_series = [(trade_date, close_price) for trade_date, _, _, _, close_price, _ in bars]
        factor_lookup = build_cumulative_factor_lookup(close_series, action_map.get(symbol, []))
        for action in action_map.get(symbol, []):
            if action.action_type == "DIVIDEND" and action.cash_amount:
                dividend_cash[symbol][action.ex_date] = action.cash_amount * factor_lookup.get(action.ex_date, 1.0)
        for trade_date, open_price, high_price, low_price, close_price, traded_value in bars:
            factor = factor_lookup.get(trade_date, 1.0)
            matrix[symbol][trade_date] = BarRecord(
                trade_date=trade_date,
                open_price=open_price * factor,
                high_price=high_price * factor,
                low_price=low_price * factor,
                close_price=close_price * factor,
                total_traded_value=traded_value,
            )
    return matrix, dividend_cash


def initialize_positions(*, bar_matrix, weights, first_date, initial_investment, costs, snapshot_by_symbol):
    cash_pool = [initial_investment]
    positions = {}
    trades = 0
    for symbol, weight in weights.items():
        bar = bar_matrix.get(symbol, {}).get(first_date)
        snapshot = snapshot_by_symbol.get(symbol)
        if bar is None or snapshot is None:
            continue
        reference_price = bar.open_price or bar.close_price
        allocation_budget = initial_investment * weight
        shares = int(allocation_budget // max(reference_price, 1.0))
        if shares <= 0:
            continue

        trade_value = shares * reference_price
        trade_costs = calculate_trade_costs(
            amount=trade_value,
            trade_date=first_date,
            is_buy=True,
            avg_traded_value=snapshot.avg_traded_value,
            annual_volatility_pct=snapshot.annual_volatility_pct,
        )
        while shares > 0 and (trade_value + trade_costs["total_costs"]) > cash_pool[0]:
            shares -= 1
            trade_value = shares * reference_price
            trade_costs = calculate_trade_costs(
                amount=trade_value,
                trade_date=first_date,
                is_buy=True,
                avg_traded_value=snapshot.avg_traded_value,
                annual_volatility_pct=snapshot.annual_volatility_pct,
            )
        if shares <= 0:
            continue

        apply_costs(costs, trade_costs)
        cash_pool[0] -= trade_value + trade_costs["total_costs"]
        positions[symbol] = {
            "shares": shares,
            "cash_pool": cash_pool,
            "lots": [{"shares": shares, "entry_price": reference_price, "entry_date": first_date}],
            "entry_price": reference_price,
            "peak_price": reference_price,
            "avg_traded_value": snapshot.avg_traded_value,
            "annual_volatility_pct": snapshot.annual_volatility_pct,
            "cooldown_until": None,
        }
        trades += 1
    return positions, trades


def rebalance_positions(position_state, bar_matrix, weights, trade_date, portfolio_value, costs, taxes, tax_buckets, risk_mode: str) -> int:
    trades = 0
    if not position_state:
        return 0
    config = RISK_MODEL_CONFIG[risk_mode]
    cash_pool = next(iter(position_state.values()))["cash_pool"]
    for symbol, state in position_state.items():
        bar = bar_matrix.get(symbol, {}).get(trade_date)
        if bar is None:
            continue
        current_value = state["shares"] * bar.close_price
        target_value = portfolio_value * weights[symbol]
        drift_value = target_value - current_value
        drift_pct = abs(drift_value) / max(portfolio_value, 1.0)
        if drift_pct < config["drift_threshold"] or abs(drift_value) < portfolio_value * config["min_trade_weight"]:
            continue
        if drift_value < 0 and state["shares"] > 0:
            shares_to_sell = int(min(abs(drift_value), current_value) // max(bar.close_price, 1.0))
            if shares_to_sell <= 0:
                continue
            proceeds = shares_to_sell * bar.close_price
            trade_costs = calculate_trade_costs(
                amount=proceeds,
                trade_date=trade_date,
                is_buy=False,
                avg_traded_value=state["avg_traded_value"],
                annual_volatility_pct=state["annual_volatility_pct"],
            )
            apply_costs(costs, trade_costs)
            cash_pool[0] += proceeds - trade_costs["total_costs"]
            realize_tax_lots(state, shares_to_sell, bar.close_price, trade_date, taxes, tax_buckets)
            state["shares"] = sum(lot["shares"] for lot in state["lots"])
            trades += 1
        elif drift_value > 0:
            if state["cooldown_until"] is not None and trade_date < state["cooldown_until"]:
                continue
            spend = min(drift_value, cash_pool[0])
            shares_to_buy = int(spend // max(bar.close_price, 1.0))
            if shares_to_buy <= 0:
                continue
            trade_value = shares_to_buy * bar.close_price
            trade_costs = calculate_trade_costs(
                amount=trade_value,
                trade_date=trade_date,
                is_buy=True,
                avg_traded_value=state["avg_traded_value"],
                annual_volatility_pct=state["annual_volatility_pct"],
            )
            total_outflow = trade_value + trade_costs["total_costs"]
            if total_outflow > cash_pool[0]:
                continue
            apply_costs(costs, trade_costs)
            cash_pool[0] -= total_outflow
            state["shares"] += shares_to_buy
            state["lots"].append({"shares": shares_to_buy, "entry_price": bar.close_price, "entry_date": trade_date})
            state["entry_price"] = weighted_average_entry_price(state["lots"])
            state["peak_price"] = max(state["peak_price"], bar.high_price)
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
    symbols = set(db.execute(select(Instrument.symbol).where(Instrument.symbol.in_(["NIFTYBEES", "JUNIORBEES", "LIQUIDBEES", "GOLDBEES"]))).scalars().all())
    if "NIFTYBEES" in symbols:
        return "NIFTYBEES"
    if "JUNIORBEES" in symbols:
        return "JUNIORBEES"
    if "LIQUIDBEES" in symbols:
        return "LIQUIDBEES"
    if "GOLDBEES" in symbols:
        return "GOLDBEES"
    return next(iter(symbols), "NIFTYBEES")


def shortlist_candidates(risk_mode: str, snapshots: list[Snapshot], candidate_count: int) -> list[Snapshot]:
    preference_order = {symbol: index for index, symbol in enumerate(RISK_MODE_UNIVERSES[risk_mode])}
    scored = sorted(
        snapshots,
        key=lambda snapshot: candidate_score(snapshot, risk_mode, preference_order.get(snapshot.symbol, 999)),
        reverse=True,
    )
    shortlisted: list[Snapshot] = []
    sector_counts: dict[str, int] = defaultdict(int)
    for snapshot in scored:
        sector_limit = 1 if len(shortlisted) < max(4, candidate_count // 2) else 2
        if sector_counts[snapshot.sector] >= sector_limit:
            continue
        shortlisted.append(snapshot)
        sector_counts[snapshot.sector] += 1
        if len(shortlisted) >= candidate_count:
            break
    return shortlisted


def align_return_matrix(snapshots: list[Snapshot]) -> tuple[list[Snapshot], list[list[float]]]:
    common_dates = None
    return_maps = {}
    for snapshot in snapshots:
        date_map = {trade_date: value for trade_date, value in snapshot.returns}
        return_maps[snapshot.symbol] = date_map
        dates = set(date_map.keys())
        common_dates = dates if common_dates is None else common_dates & dates
    ordered_dates = sorted(common_dates or [])
    if len(ordered_dates) < 20:
        return [], [[]]
    matrix = [[return_maps[snapshot.symbol][trade_date] for trade_date in ordered_dates] for snapshot in snapshots]
    return snapshots, matrix


def estimate_expected_returns(db, as_of_date,
    snapshots: list[Snapshot],
    return_matrix: list[list[float]],
    risk_mode: str,
    model_variant: ModelVariant = "RULES",
) -> list[float]:
    # 1) Compute rule-based expected returns (always).
    regime = detect_market_regime(snapshots)
    rule_expected_returns: list[float] = []
    config = RISK_MODEL_CONFIG[risk_mode]
    for index, snapshot in enumerate(snapshots):
        series = return_matrix[index]
        daily_mean = sum(series) / max(len(series), 1)
        annual_mean = daily_mean * 252
        momentum = snapshot.factor_scores.get("momentum", 0.0)
        quality = snapshot.factor_scores.get("quality", 0.0)
        low_vol = snapshot.factor_scores.get("low_vol", 0.0)
        liquidity = snapshot.factor_scores.get("liquidity", 0.0)
        sector_strength = snapshot.factor_scores.get("sector_strength", 0.0)
        size = snapshot.factor_scores.get("size", 0.0)
        beta_score = snapshot.factor_scores.get("beta", 0.0)
        if risk_mode == "ULTRA_LOW":
            factor_alpha = (
                (0.28 * quality)
                + (0.24 * low_vol)
                + (0.12 * liquidity)
                + (0.10 * sector_strength)
                + (0.06 * size)
                - (0.12 * abs(snapshot.beta_proxy - 0.65))
            )
            defensive_bonus = 0.02 if snapshot.instrument_type == "ETF" or snapshot.sector in {"Gold", "Liquid", "FMCG", "Pharma"} else 0.0
            expected = regime["base_return"] + (0.30 * annual_mean) + (0.028 * factor_alpha) + defensive_bonus
        elif risk_mode == "HIGH":
            factor_alpha = (
                (0.38 * momentum)
                + (0.18 * sector_strength)
                + (0.10 * quality)
                + (0.08 * liquidity)
                - (0.05 * low_vol)
                - (0.07 * size)
                + (0.16 * beta_score)
            )
            cyclical_bonus = 0.01 if snapshot.sector in {"Auto", "Tech/Internet", "Infra", "Real Estate", "Energy"} else 0.0
            expected = regime["base_return"] + regime["risk_on_bonus"] + (0.42 * annual_mean) + (0.035 * factor_alpha) + cyclical_bonus
        else:
            factor_alpha = (
                (0.28 * momentum)
                + (0.24 * quality)
                + (0.18 * low_vol)
                + (0.10 * liquidity)
                + (0.08 * sector_strength)
                + (0.04 * size)
                - (0.06 * abs(snapshot.beta_proxy - 1.0))
            )
            expected = regime["base_return"] + (0.36 * annual_mean) + (0.030 * factor_alpha)
        expected -= config["turnover_penalty"] * max(0.0, abs(snapshot.beta_proxy - 1.0) - 0.15) * 0.01
        rule_expected_returns.append(max(-0.15, min(0.35, expected)))

    # 2) Default to rule-only, and annotate snapshot metadata accordingly.
    for snapshot in snapshots:
        snapshot.expected_return_source = "RULES"
        snapshot.model_version = "rules"
        snapshot.ml_pred_21d_return = None
        snapshot.ml_pred_annual_return = None
        snapshot.top_model_drivers = []

    if model_variant != "LIGHTGBM_HYBRID":
        return rule_expected_returns

    # 3) Hybrid mode: blend ML calibrated annual return into the rule engine.
    #    Only apply ML predictions to delivery equities; keep ETFs stable.
    try:
        from app.ml.ensemble_alpha.predict import EnsembleAlphaPredictor

        predictor = EnsembleAlphaPredictor()
        predictions_by_symbol, model_info = predictor.predict(db, snapshots, as_of_date)
    except Exception:
        predictions_by_symbol, model_info = {}, {"available": False}

    model_version = str(model_info.get("model_version", "unknown"))

    expected_returns = rule_expected_returns[:]
    any_ml_used = False
    for i, snapshot in enumerate(snapshots):
        symbol = snapshot.symbol
        pred = predictions_by_symbol.get(symbol)
        if snapshot.instrument_type != "EQUITY" or pred is None:
            continue
        expected_ml_annual = pred.pred_annual_return
        blended = 0.75 * expected_ml_annual + 0.25 * rule_expected_returns[i]
        expected_returns[i] = max(-0.15, min(0.35, blended))

        snapshot.ml_pred_21d_return = float(pred.pred_21d_return)
        snapshot.ml_pred_annual_return = float(expected_ml_annual)
        snapshot.top_model_drivers = list(pred.top_drivers)
        snapshot.expected_return_source = str(model_info.get("model_source", "ENSEMBLE"))
        snapshot.model_version = model_version
        snapshot.prediction_horizon_days = int(model_info.get("prediction_horizon_days", 21))
        any_ml_used = True

    return expected_returns


def build_shrunk_covariance(return_matrix: list[list[float]], shrinkage: float) -> list[list[float]]:
    asset_count = len(return_matrix)
    if asset_count == 0:
        return []
    sample = [[0.0 for _ in range(asset_count)] for _ in range(asset_count)]
    for row in range(asset_count):
        for col in range(asset_count):
            sample[row][col] = covariance(return_matrix[row], return_matrix[col]) * 252
    diagonal = [[0.0 for _ in range(asset_count)] for _ in range(asset_count)]
    for index in range(asset_count):
        diagonal[index][index] = sample[index][index]
    return [
        [
            ((1 - shrinkage) * sample[row][col]) + (shrinkage * diagonal[row][col])
            for col in range(asset_count)
        ]
        for row in range(asset_count)
    ]


def optimize_constrained_allocator(
    snapshots: list[Snapshot],
    expected_returns: list[float],
    covariance_matrix: list[list[float]],
    risk_mode: str,
) -> list[float]:
    config = RISK_MODEL_CONFIG[risk_mode]
    if not snapshots:
        return []

    prior = build_prior_weights(snapshots, risk_mode)
    weights = prior[:]
    for iteration in range(240):
        sigma_w = matrix_vector_product(covariance_matrix, weights)
        gradient = []
        for index, snapshot in enumerate(snapshots):
            factor_bonus = 0.01 * snapshot.factor_scores.get("quality", 0.0) if risk_mode != "HIGH" else 0.012 * snapshot.factor_scores.get("momentum", 0.0)
            etf_bonus = 0.01 if snapshot.instrument_type == "ETF" and risk_mode == "ULTRA_LOW" else 0.0
            gradient.append(expected_returns[index] + factor_bonus + etf_bonus - (config["risk_aversion"] * sigma_w[index]))
        step_size = 0.18 / (1 + (iteration / 30))
        proposal = [(weight + (step_size * grad)) for weight, grad in zip(weights, gradient)]
        weights = project_weights(proposal, snapshots, risk_mode, prior)

    cleaned = [weight if weight >= 0.005 else 0.0 for weight in weights]
    return renormalize(cleaned)


def build_prior_weights(snapshots: list[Snapshot], risk_mode: str) -> list[float]:
    raw = []
    for snapshot in snapshots:
        if risk_mode == "ULTRA_LOW":
            score = max(0.05, 1.0 + (0.5 * snapshot.factor_scores.get("low_vol", 0.0)) + (0.35 * snapshot.factor_scores.get("quality", 0.0)) + (0.15 if snapshot.instrument_type == "ETF" else 0.0))
        elif risk_mode == "HIGH":
            score = max(0.05, 1.0 + (0.55 * snapshot.factor_scores.get("momentum", 0.0)) + (0.20 * snapshot.factor_scores.get("quality", 0.0)) + (0.20 * snapshot.factor_scores.get("beta", 0.0)))
        else:
            score = max(0.05, 1.0 + (0.35 * snapshot.factor_scores.get("momentum", 0.0)) + (0.35 * snapshot.factor_scores.get("quality", 0.0)) + (0.20 * snapshot.factor_scores.get("low_vol", 0.0)))
        raw.append(score)
    total = sum(raw)
    return [value / max(total, 1e-9) for value in raw]


def project_weights(weights: list[float], snapshots: list[Snapshot], risk_mode: str, prior: list[float]) -> list[float]:
    config = RISK_MODEL_CONFIG[risk_mode]
    projected = [min(config["max_weight"], max(0.0, weight)) for weight in weights]
    projected = renormalize(projected)
    for _ in range(6):
        sector_totals = compute_sector_totals(projected, snapshots)
        excess_pool = 0.0
        for sector, total in sector_totals.items():
            if total <= config["sector_cap"]:
                continue
            scale = config["sector_cap"] / max(total, 1e-9)
            for index, snapshot in enumerate(snapshots):
                if snapshot.sector == sector:
                    reduced = projected[index] * (1 - scale)
                    projected[index] *= scale
                    excess_pool += reduced
        if excess_pool <= 1e-9:
            break
        projected = redistribute_weight(projected, snapshots, risk_mode, prior, excess_pool)
    return renormalize([min(config["max_weight"], max(0.0, weight)) for weight in projected])


def redistribute_weight(weights: list[float], snapshots: list[Snapshot], risk_mode: str, prior: list[float], excess_pool: float) -> list[float]:
    config = RISK_MODEL_CONFIG[risk_mode]
    sector_totals = compute_sector_totals(weights, snapshots)
    headroom = []
    for index, snapshot in enumerate(snapshots):
        asset_headroom = max(0.0, config["max_weight"] - weights[index])
        sector_headroom = max(0.0, config["sector_cap"] - sector_totals[snapshot.sector])
        score = min(asset_headroom, sector_headroom) * (1.0 + max(prior[index], 0.001))
        headroom.append(score)
    total_headroom = sum(headroom)
    if total_headroom <= 1e-9:
        return weights
    redistributed = weights[:]
    for index, score in enumerate(headroom):
        redistributed[index] += excess_pool * (score / total_headroom)
    return redistributed


def compute_sector_totals(weights: list[float], snapshots: list[Snapshot]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for index, snapshot in enumerate(snapshots):
        totals[snapshot.sector] += weights[index]
    return totals


def renormalize(weights: list[float]) -> list[float]:
    total = sum(weights)
    if total <= 1e-9:
        equal = 1 / max(len(weights), 1)
        return [equal for _ in weights]
    return [weight / total for weight in weights]


def matrix_vector_product(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(cell * vector[column] for column, cell in enumerate(row)) for row in matrix]


def candidate_score(snapshot: Snapshot, risk_mode: str, preference_rank: int) -> float:
    preference_bonus = max(0.0, 12.0 - preference_rank)
    liquidity_bonus = min(snapshot.avg_traded_value / 50_000_000.0, 10.0)
    if risk_mode == "ULTRA_LOW":
        return (
            (22.0 * snapshot.factor_scores.get("low_vol", 0.0))
            + (18.0 * snapshot.factor_scores.get("quality", 0.0))
            + max(0.0, 16.0 - abs(snapshot.beta_proxy - 0.6) * 10.0)
            + (8.0 if snapshot.instrument_type == "ETF" else 0.0)
            + preference_bonus
            + liquidity_bonus
        )
    if risk_mode == "HIGH":
        return (
            (24.0 * snapshot.factor_scores.get("momentum", 0.0))
            + (12.0 * snapshot.factor_scores.get("sector_strength", 0.0))
            + (6.0 * snapshot.factor_scores.get("beta", 0.0))
            + (4.0 * snapshot.factor_scores.get("liquidity", 0.0))
            + preference_bonus
            + liquidity_bonus
        )
    return (
        (16.0 * snapshot.factor_scores.get("momentum", 0.0))
        + (16.0 * snapshot.factor_scores.get("quality", 0.0))
        + (10.0 * snapshot.factor_scores.get("low_vol", 0.0))
        + (6.0 * snapshot.factor_scores.get("sector_strength", 0.0))
        + preference_bonus
        + liquidity_bonus
    )


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
    if not values:
        return 0.0
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / max(peak, 1e-9))
    return max_drawdown


def calculate_trade_costs(amount: float, trade_date: date, *, is_buy: bool, avg_traded_value: float, annual_volatility_pct: float) -> dict[str, float]:
    schedule = resolve_equity_fee_schedule(trade_date)
    brokerage = min(amount * schedule.brokerage_rate, schedule.max_brokerage_per_order)
    stt = amount * (schedule.stt_buy_rate if is_buy else schedule.stt_sell_rate)
    stamp_duty = amount * schedule.stamp_duty_buy_rate if is_buy else 0.0
    exchange_txn = amount * schedule.exchange_txn_rate
    sebi_fee = amount * schedule.sebi_fee_rate
    gst = (brokerage + exchange_txn + sebi_fee) * schedule.gst_rate
    slippage = amount * liquidity_adjusted_slippage_rate(amount, avg_traded_value, annual_volatility_pct)
    total_costs = brokerage + stt + stamp_duty + exchange_txn + sebi_fee + gst + slippage
    return {
        "total_brokerage": brokerage,
        "total_stt": stt,
        "total_stamp_duty": stamp_duty,
        "total_exchange_txn": exchange_txn,
        "total_sebi_fees": sebi_fee,
        "total_gst": gst,
        "total_slippage": slippage,
        "total_costs": total_costs,
    }


def apply_costs(cost_bucket: dict[str, float], trade_costs: dict[str, float]) -> None:
    for key, value in trade_costs.items():
        cost_bucket[key] += value


def round_mapping(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}


def liquidity_adjusted_slippage_rate(amount: float, avg_traded_value: float, annual_volatility_pct: float) -> float:
    participation = amount / max(avg_traded_value, 1.0)
    volatility_load = max(0.0, annual_volatility_pct - 15.0) / 10_000.0
    return min(0.006, 0.0005 + min(0.004, participation * 0.08) + volatility_load)


def populate_factor_scores(snapshots: list[Snapshot]) -> None:
    if not snapshots:
        return

    sector_average_momentum: dict[str, float] = defaultdict(float)
    sector_counts: dict[str, int] = defaultdict(int)
    for snapshot in snapshots:
        sector_average_momentum[snapshot.sector] += blended_momentum(snapshot)
        sector_counts[snapshot.sector] += 1
    for sector in sector_average_momentum:
        sector_average_momentum[sector] /= max(sector_counts[sector], 1)

    raw_factor_values = {
        "momentum": {snapshot.symbol: blended_momentum(snapshot) for snapshot in snapshots},
        "quality": {snapshot.symbol: quality_proxy(snapshot) for snapshot in snapshots},
        "low_vol": {snapshot.symbol: -snapshot.annual_volatility_pct for snapshot in snapshots},
        "liquidity": {snapshot.symbol: sqrt(max(snapshot.avg_traded_value, 1.0)) for snapshot in snapshots},
        "sector_strength": {snapshot.symbol: blended_momentum(snapshot) - sector_average_momentum[snapshot.sector] for snapshot in snapshots},
        "size": {snapshot.symbol: market_cap_bucket_score(snapshot.market_cap_bucket) for snapshot in snapshots},
        "beta": {snapshot.symbol: snapshot.beta_proxy - 1.0 for snapshot in snapshots},
    }

    zscores = {factor: zscore_map(values) for factor, values in raw_factor_values.items()}
    for snapshot in snapshots:
        snapshot.factor_scores = {factor: zscores[factor].get(snapshot.symbol, 0.0) for factor in FACTOR_KEYS}


def blended_momentum(snapshot: Snapshot) -> float:
    return (0.20 * snapshot.momentum_1m_pct) + (0.35 * snapshot.momentum_3m_pct) + (0.45 * snapshot.momentum_6m_pct)


def quality_proxy(snapshot: Snapshot) -> float:
    return (
        snapshot.annual_return_pct
        - (0.70 * snapshot.downside_volatility_pct)
        - (0.40 * snapshot.max_drawdown_pct)
        + max(0.0, 18.0 - abs(snapshot.beta_proxy - 1.0) * 8.0)
    )


def market_cap_bucket_score(bucket: str | None) -> float:
    if bucket == "Large":
        return 1.0
    if bucket == "Mid":
        return 0.0
    if bucket == "Small":
        return -1.0
    return -0.25


def zscore_map(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    series = list(values.values())
    mean_value = sum(series) / len(series)
    std_value = sqrt(sum((value - mean_value) ** 2 for value in series) / max(len(series) - 1, 1))
    if std_value <= 1e-9:
        return {key: 0.0 for key in values}
    return {key: (value - mean_value) / std_value for key, value in values.items()}


def compute_factor_exposures(weighted_snapshots: list[tuple[Snapshot, float]]) -> dict[str, float]:
    exposures = {factor: 0.0 for factor in FACTOR_KEYS}
    total_weight = sum(weight for _, weight in weighted_snapshots)
    if total_weight <= 1e-9:
        return exposures
    for snapshot, weight in weighted_snapshots:
        normalized = weight / total_weight
        for factor in FACTOR_KEYS:
            exposures[factor] += snapshot.factor_scores.get(factor, 0.0) * normalized
    return exposures


def detect_market_regime(snapshots: list[Snapshot]) -> dict[str, float]:
    benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
    if benchmark is None:
        benchmark = max(snapshots, key=lambda snapshot: snapshot.avg_traded_value, default=None)
    if benchmark is None:
        return {"base_return": 0.10, "risk_on_bonus": 0.0}
    trailing_return = benchmark.momentum_3m_pct
    trailing_vol = benchmark.annual_volatility_pct
    if trailing_return < -5.0 or trailing_vol > 24.0:
        return {"base_return": 0.08, "risk_on_bonus": -0.01}
    if trailing_return > 8.0 and trailing_vol < 18.0:
        return {"base_return": 0.12, "risk_on_bonus": 0.015}
    return {"base_return": 0.10, "risk_on_bonus": 0.0}


def build_nifty50_proxy_portfolio(snapshots: list[Snapshot]) -> dict[str, float]:
    equities = [snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY" and snapshot.market_cap_bucket == "Large"]
    ranked = sorted(equities, key=lambda snapshot: snapshot.avg_traded_value, reverse=True)[:50]
    if not ranked:
        etf = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
        return {etf.symbol: 1.0} if etf else {}
    weights = {snapshot.symbol: sqrt(max(snapshot.avg_traded_value, 1.0)) for snapshot in ranked}
    return normalize_score_weights(weights)


def build_nifty500_proxy_portfolio(snapshots: list[Snapshot]) -> dict[str, float]:
    equities = [snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY"]
    bucket_targets = {"Large": 0.70, "Mid": 0.20, "Small": 0.10}
    ranked_by_bucket: dict[str, list[Snapshot]] = defaultdict(list)
    for snapshot in sorted(equities, key=lambda item: item.avg_traded_value, reverse=True):
        ranked_by_bucket[snapshot.market_cap_bucket or "Small"].append(snapshot)

    weights: dict[str, float] = {}
    for bucket, target_weight in bucket_targets.items():
        members = ranked_by_bucket.get(bucket, [])[: min(40, max(8, len(ranked_by_bucket.get(bucket, []))))]
        if not members:
            continue
        bucket_weight = target_weight / len(members)
        for snapshot in members:
            weights[snapshot.symbol] = weights.get(snapshot.symbol, 0.0) + bucket_weight
    return normalize_score_weights(weights)


def build_factor_portfolio(snapshots: list[Snapshot], *, factor_key: str, count: int, sector_cap: float) -> dict[str, float]:
    equities = [snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY"]
    ranked = sorted(equities, key=lambda snapshot: snapshot.factor_scores.get(factor_key, 0.0), reverse=True)[:count]
    if not ranked:
        return {}
    score_weights = {snapshot.symbol: max(0.05, 1.0 + snapshot.factor_scores.get(factor_key, 0.0)) for snapshot in ranked}
    return cap_sector_weights(normalize_score_weights(score_weights), {snapshot.symbol: snapshot for snapshot in ranked}, sector_cap)


def build_multifactor_portfolio(snapshots: list[Snapshot], *, count: int, sector_cap: float) -> dict[str, float]:
    equities = [snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY"]
    ranked = sorted(
        equities,
        key=lambda snapshot: (
            (0.35 * snapshot.factor_scores.get("momentum", 0.0))
            + (0.35 * snapshot.factor_scores.get("quality", 0.0))
            + (0.20 * snapshot.factor_scores.get("low_vol", 0.0))
            + (0.10 * snapshot.factor_scores.get("liquidity", 0.0))
        ),
        reverse=True,
    )[:count]
    if not ranked:
        return {}
    score_weights = {
        snapshot.symbol: max(
            0.05,
            1.0
            + (0.35 * snapshot.factor_scores.get("momentum", 0.0))
            + (0.35 * snapshot.factor_scores.get("quality", 0.0))
            + (0.20 * snapshot.factor_scores.get("low_vol", 0.0))
            + (0.10 * snapshot.factor_scores.get("liquidity", 0.0)),
        )
        for snapshot in ranked
    }
    return cap_sector_weights(normalize_score_weights(score_weights), {snapshot.symbol: snapshot for snapshot in ranked}, sector_cap)


def normalize_score_weights(raw_weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(value, 0.0) for value in raw_weights.values())
    if total <= 1e-9:
        return {}
    return {symbol: max(value, 0.0) / total for symbol, value in raw_weights.items()}


def cap_sector_weights(weights: dict[str, float], snapshot_map: dict[str, Snapshot], sector_cap: float) -> dict[str, float]:
    adjusted = dict(weights)
    for _ in range(4):
        sector_totals: dict[str, float] = defaultdict(float)
        for symbol, weight in adjusted.items():
            snapshot = snapshot_map.get(symbol)
            if snapshot is not None:
                sector_totals[snapshot.sector] += weight
        excess_pool = 0.0
        capped_sectors = {sector for sector, total in sector_totals.items() if total >= sector_cap - 1e-9}
        for sector, total in sector_totals.items():
            if total <= sector_cap:
                continue
            scale = sector_cap / max(total, 1e-9)
            for symbol, weight in list(adjusted.items()):
                snapshot = snapshot_map.get(symbol)
                if snapshot and snapshot.sector == sector:
                    reduced = weight * (1 - scale)
                    adjusted[symbol] = weight * scale
                    excess_pool += reduced
        if excess_pool <= 1e-9:
            break
        eligible = [symbol for symbol in adjusted if snapshot_map[symbol].sector not in capped_sectors]
        if not eligible:
            break
        add_on = excess_pool / len(eligible)
        for symbol in eligible:
            adjusted[symbol] += add_on
        adjusted = normalize_score_weights(adjusted)
    return normalize_score_weights(adjusted)


def determine_exit_fill(bar: BarRecord, state, risk_mode: str, stop_loss_pct: float, take_profit_pct: float) -> tuple[float | None, str | None]:
    reference_for_stop = state["peak_price"] if risk_mode == "HIGH" else state["entry_price"]
    stop_level = reference_for_stop * (1 - stop_loss_pct)
    take_level = state["entry_price"] * (1 + take_profit_pct)
    if bar.low_price <= stop_level:
        return (bar.open_price if bar.open_price <= stop_level else stop_level), "STOP"
    if bar.high_price >= take_level:
        return (bar.open_price if bar.open_price >= take_level else take_level), "TAKE_PROFIT"
    return None, None


def is_long_term_equity_holding(entry_date: date, trade_date: date) -> bool:
    try:
        anniversary = entry_date.replace(year=entry_date.year + 1)
    except ValueError:
        # Handle leap-day entries by rolling to Feb 28 in the next year.
        anniversary = entry_date.replace(year=entry_date.year + 1, month=2, day=28)
    return trade_date >= anniversary


def realize_tax_lots(state, shares_to_sell: int, sell_price: float, trade_date: date, taxes: dict[str, float], tax_buckets: dict[str, dict]) -> None:
    remaining = shares_to_sell
    while remaining > 0 and state["lots"]:
        lot = state["lots"][0]
        quantity = min(remaining, lot["shares"])
        gain = quantity * (sell_price - lot["entry_price"])
        schedule = resolve_capital_gains_tax_schedule(trade_date)
        fiscal_year = financial_year_for_trade_date(trade_date)
        if not is_long_term_equity_holding(lot["entry_date"], trade_date):
            taxes["stcg_gain"] += gain
            tax_buckets["stcg"][(fiscal_year, schedule.stcg_rate, schedule.cess_rate)] += gain
        else:
            taxes["ltcg_gain"] += gain
            bucket_key = (fiscal_year, schedule.ltcg_rate, schedule.ltcg_exemption, schedule.cess_rate)
            if gain >= 0:
                tax_buckets["ltcg_positive"][bucket_key] += gain
            else:
                tax_buckets["ltcg_negative"][bucket_key] += gain
        lot["shares"] -= quantity
        remaining -= quantity
        if lot["shares"] <= 0:
            state["lots"].pop(0)


def finalize_tax_buckets(taxes: dict[str, float], tax_buckets: dict[str, dict]) -> None:
    stcg_tax = 0.0
    ltcg_tax = 0.0
    cess_tax = 0.0

    for (_, rate, cess_rate), gain in tax_buckets["stcg"].items():
        taxable_gain = max(0.0, gain)
        base_tax = taxable_gain * rate
        stcg_tax += base_tax
        cess_tax += base_tax * cess_rate

    ltcg_by_fy: dict[str, list[tuple[float, float, float, float]]] = defaultdict(list)
    for (fiscal_year, rate, exemption, cess_rate), gain in tax_buckets["ltcg_positive"].items():
        ltcg_by_fy[fiscal_year].append((gain, rate, exemption, cess_rate))
    for (fiscal_year, rate, exemption, cess_rate), gain in tax_buckets["ltcg_negative"].items():
        ltcg_by_fy[fiscal_year].append((gain, rate, exemption, cess_rate))

    for entries in ltcg_by_fy.values():
        positive_total = sum(max(0.0, gain) for gain, _, _, _ in entries)
        net_total = sum(gain for gain, _, _, _ in entries)
        if positive_total <= 0 or net_total <= 0:
            continue
        exemption = max(exemption for _, _, exemption, _ in entries)
        taxable_total = max(0.0, net_total - exemption)
        for gain, rate, _, cess_rate in entries:
            positive_gain = max(0.0, gain)
            if positive_gain <= 0:
                continue
            allocated_taxable = taxable_total * (positive_gain / positive_total)
            base_tax = allocated_taxable * rate
            ltcg_tax += base_tax
            cess_tax += base_tax * cess_rate

    taxes["stcg_tax"] = stcg_tax
    taxes["ltcg_tax"] = ltcg_tax
    taxes["cess_tax"] = cess_tax
    taxes["total_tax"] = stcg_tax + ltcg_tax + cess_tax


def weighted_average_entry_price(lots: list[dict[str, object]]) -> float:
    total_shares = sum(int(lot["shares"]) for lot in lots)
    if total_shares <= 0:
        return 0.0
    total_cost = sum(int(lot["shares"]) * float(lot["entry_price"]) for lot in lots)
    return total_cost / total_shares


def current_portfolio_value(position_state, bar_matrix, trade_date: date) -> float:
    if not position_state:
        return 0.0
    value = next(iter(position_state.values()))["cash_pool"][0]
    for symbol, state in position_state.items():
        bar = bar_matrix.get(symbol, {}).get(trade_date)
        if bar is not None:
            value += state["shares"] * bar.close_price
    return value
