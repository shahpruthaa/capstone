from __future__ import annotations

from datetime import date, timedelta

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


MODEL_PORTFOLIOS = {
    "ULTRA_LOW": [
        ("LIQUIDBEES", "Liquid", 35.0, "Cash-equivalent liquidity sleeve."),
        ("GOLDBEES", "Gold", 20.0, "Macro hedge and drawdown ballast."),
        ("HDFCBANK", "Banking", 10.0, "Large-cap financial stability."),
        ("ITC", "FMCG", 10.0, "Defensive cash-generative exposure."),
        ("SUNPHARMA", "Pharma", 10.0, "Defensive earnings profile."),
        ("POWERGRID", "Energy", 7.5, "Utility-style dividend support."),
        ("BHARTIARTL", "Telecom", 7.5, "Low-beta cash flow exposure."),
    ],
    "MODERATE": [
        ("HDFCBANK", "Banking", 12.0, "Core financial compounder."),
        ("TCS", "IT", 11.0, "Quality large-cap exporter."),
        ("INFY", "IT", 8.0, "Diversified technology earnings."),
        ("RELIANCE", "Energy", 10.0, "Large-cap diversified growth."),
        ("SUNPHARMA", "Pharma", 9.0, "Defensive growth buffer."),
        ("HINDUNILVR", "FMCG", 8.0, "Low-volatility defensive sleeve."),
        ("BHARTIARTL", "Telecom", 8.0, "Recurring cash-flow exposure."),
        ("GOLDBEES", "Gold", 10.0, "Crisis hedge allocation."),
        ("LIQUIDBEES", "Liquid", 8.0, "Dry powder for rebalancing."),
        ("LT", "Infra", 8.0, "Capex and infrastructure exposure."),
        ("ICICIBANK", "Banking", 8.0, "Balanced financial growth."),
    ],
    "HIGH": [
        ("TATAMOTORS", "Auto", 12.0, "High-beta cyclical growth."),
        ("COFORGE", "IT", 10.0, "Mid-cap momentum technology."),
        ("KPITTECH", "IT", 10.0, "EV/software growth sleeve."),
        ("ADANIGREEN", "Energy", 10.0, "Aggressive renewables exposure."),
        ("ZOMATO", "Tech/Internet", 10.0, "Platform-led growth."),
        ("PERSISTENT", "IT", 8.0, "High-growth services exposure."),
        ("DLF", "Real Estate", 8.0, "Property cycle upside."),
        ("MUTHOOTFIN", "Finance", 7.0, "Non-bank financial carry."),
        ("BHEL", "Infra", 7.0, "Capital goods momentum."),
        ("DIVISLAB", "Pharma", 8.0, "Defensive alpha ballast."),
        ("GOLDBEES", "Gold", 5.0, "Small hedge sleeve."),
        ("INDUSINDBK", "Banking", 5.0, "Higher-risk financial beta."),
    ],
}


PORTFOLIO_METRICS = {
    "ULTRA_LOW": PortfolioMetricsModel(
        estimated_return_pct=8.5,
        estimated_volatility_pct=6.2,
        beta=0.38,
        diversification_score=79.0,
    ),
    "MODERATE": PortfolioMetricsModel(
        estimated_return_pct=13.8,
        estimated_volatility_pct=14.1,
        beta=0.86,
        diversification_score=74.0,
    ),
    "HIGH": PortfolioMetricsModel(
        estimated_return_pct=19.6,
        estimated_volatility_pct=24.8,
        beta=1.32,
        diversification_score=66.0,
    ),
}


def generate_portfolio(payload: GeneratePortfolioRequest) -> GeneratePortfolioResponse:
    template = MODEL_PORTFOLIOS[payload.risk_mode]
    allocations = [
        AllocationModel(symbol=symbol, sector=sector, weight=weight, rationale=rationale)
        for symbol, sector, weight, rationale in template
    ]

    notes = [
        "This is a scaffold response from the Python backend and will be replaced by a factor-driven optimizer.",
        "Target production flow: universe filter -> factor scoring -> shrinkage covariance -> constrained optimizer.",
        "Weights should eventually be computed against dated market data and user constraints, not templates.",
    ]

    return GeneratePortfolioResponse(
        risk_mode=payload.risk_mode,
        investment_amount=payload.investment_amount,
        allocations=allocations,
        metrics=PORTFOLIO_METRICS[payload.risk_mode],
        notes=notes,
    )


def analyze_portfolio(payload: AnalyzePortfolioRequest) -> AnalyzePortfolioResponse:
    portfolio_value = float(sum((holding.average_price or 1000.0) * holding.quantity for holding in payload.holdings))
    sector_weights = {
        "Banking": 28.0,
        "IT": 22.0,
        "FMCG": 12.0,
        "Pharma": 14.0,
        "Energy": 10.0,
        "Gold": 14.0,
    }

    actions = [
        RebalanceActionModel(
            symbol="BANKING_BASKET",
            action="SELL",
            target_weight=20.0,
            current_weight=28.0,
            reason="Banking concentration is above the target risk budget.",
        ),
        RebalanceActionModel(
            symbol="GOLDBEES",
            action="BUY",
            target_weight=10.0 if payload.target_risk_mode == "HIGH" else 15.0,
            current_weight=6.0,
            reason="A hedge sleeve improves diversification and drawdown control.",
        ),
        RebalanceActionModel(
            symbol="SUNPHARMA",
            action="BUY",
            target_weight=8.0,
            current_weight=2.0,
            reason="Defensive pharma exposure offsets cyclical risk.",
        ),
    ]

    notes = [
        "This analyzer currently returns scaffolded exposure diagnostics.",
        "Next implementation should compute empirical covariance and factor exposure from ingested NSE histories.",
    ]

    correlation_risk = "MODERATE"
    if payload.target_risk_mode == "HIGH":
        correlation_risk = "HIGH"

    return AnalyzePortfolioResponse(
        total_holdings=len(payload.holdings),
        portfolio_value=portfolio_value,
        current_beta=0.92 if payload.target_risk_mode != "HIGH" else 1.24,
        diversification_score=68.0 if payload.target_risk_mode != "HIGH" else 54.0,
        sector_weights=sector_weights,
        correlation_risk=correlation_risk,
        actions=actions,
        notes=notes,
    )


def run_backtest(payload: BacktestRequest) -> BacktestResultResponse:
    run_id = f"bt-{payload.start_date.isoformat()}-{payload.end_date.isoformat()}-{payload.risk_mode.lower()}"
    return _build_backtest_response(run_id, payload.start_date, payload.end_date, payload.risk_mode)


def get_backtest_result(run_id: str) -> BacktestResultResponse:
    return _build_backtest_response(run_id, date(2022, 1, 1), date(2025, 1, 1), "MODERATE")


def _build_backtest_response(run_id: str, start_date: date, end_date: date, risk_mode: str) -> BacktestResultResponse:
    metrics_by_mode = {
        "ULTRA_LOW": BacktestMetricModel(
            cagr_pct=8.2,
            total_return_pct=27.4,
            max_drawdown_pct=5.4,
            sharpe_ratio=1.18,
            sortino_ratio=1.62,
            calmar_ratio=1.52,
            turnover_pct=18.0,
            win_rate_pct=57.0,
            total_trades=14,
            tax_drag_pct=0.7,
            cost_drag_pct=0.35,
            final_value=1_274_000.0,
            initial_investment=1_000_000.0,
        ),
        "MODERATE": BacktestMetricModel(
            cagr_pct=14.6,
            total_return_pct=50.8,
            max_drawdown_pct=12.8,
            sharpe_ratio=1.24,
            sortino_ratio=1.71,
            calmar_ratio=1.14,
            turnover_pct=34.0,
            win_rate_pct=59.0,
            total_trades=29,
            tax_drag_pct=1.3,
            cost_drag_pct=0.62,
            final_value=1_508_000.0,
            initial_investment=1_000_000.0,
        ),
        "HIGH": BacktestMetricModel(
            cagr_pct=19.8,
            total_return_pct=72.3,
            max_drawdown_pct=24.6,
            sharpe_ratio=1.06,
            sortino_ratio=1.43,
            calmar_ratio=0.80,
            turnover_pct=61.0,
            win_rate_pct=54.0,
            total_trades=48,
            tax_drag_pct=2.4,
            cost_drag_pct=1.08,
            final_value=1_723_000.0,
            initial_investment=1_000_000.0,
        ),
    }

    taxes_by_mode = {
        "ULTRA_LOW": TaxBreakdownModel(stcg_gain=24_000, ltcg_gain=96_000, stcg_tax=4_800, ltcg_tax=0, total_tax=4_800),
        "MODERATE": TaxBreakdownModel(stcg_gain=72_000, ltcg_gain=138_000, stcg_tax=14_400, ltcg_tax=1_625, total_tax=16_025),
        "HIGH": TaxBreakdownModel(stcg_gain=158_000, ltcg_gain=174_000, stcg_tax=31_600, ltcg_tax=6_125, total_tax=37_725),
    }

    costs_by_mode = {
        "ULTRA_LOW": CostBreakdownModel(total_brokerage=620, total_stt=1_520, total_stamp_duty=220, total_gst=112, total_slippage=1_040, total_costs=3_512),
        "MODERATE": CostBreakdownModel(total_brokerage=1_240, total_stt=3_860, total_stamp_duty=540, total_gst=224, total_slippage=2_780, total_costs=8_644),
        "HIGH": CostBreakdownModel(total_brokerage=2_220, total_stt=7_420, total_stamp_duty=980, total_gst=400, total_slippage=5_640, total_costs=16_660),
    }

    total_days = max((end_date - start_date).days, 180)
    step = max(total_days // 6, 30)
    points: list[CurvePointModel] = []
    base_portfolio = metrics_by_mode[risk_mode].initial_investment
    base_benchmark = metrics_by_mode[risk_mode].initial_investment
    target_portfolio = metrics_by_mode[risk_mode].final_value
    target_benchmark = base_benchmark * 1.35

    current_date = start_date
    increment = 0
    total_steps = max(((end_date - start_date).days // step) + 1, 1)

    while current_date <= end_date:
        progress = min(increment / total_steps, 1)
        points.append(
            CurvePointModel(
                date=current_date,
                portfolio_value=round(base_portfolio + ((target_portfolio - base_portfolio) * progress), 2),
                benchmark_value=round(base_benchmark + ((target_benchmark - base_benchmark) * progress), 2),
            )
        )
        increment += 1
        if current_date == end_date:
            break
        current_date = min(current_date + timedelta(days=step), end_date)

    return BacktestResultResponse(
        run_id=run_id,
        status="completed",
        metrics=metrics_by_mode[risk_mode],
        tax_liability=taxes_by_mode[risk_mode],
        cost_breakdown=costs_by_mode[risk_mode],
        equity_curve=points,
        notes=[
            "This is a scaffolded historical replay response.",
            "Production backtests will use adjusted OHLCV, liquidity-aware slippage, dated fees, and FIFO tax lots.",
        ],
    )


def get_benchmark_summary() -> BenchmarkSummaryResponse:
    strategies = [
        BenchmarkMetricModel(
            name="NSE AI Portfolio",
            description="Correlation-aware multi-factor portfolio with tax and cost overlays.",
            category="AI",
            annual_return_pct=16.4,
            volatility_pct=13.2,
            sharpe_ratio=1.31,
            sortino_ratio=1.78,
            max_drawdown_pct=10.8,
            cagr_5y_pct=15.6,
            expense_ratio_pct=0.08,
        ),
        BenchmarkMetricModel(
            name="Nifty 50",
            description="Large-cap market benchmark for broad Indian equity exposure.",
            category="INDEX",
            annual_return_pct=12.2,
            volatility_pct=15.9,
            sharpe_ratio=0.92,
            sortino_ratio=1.24,
            max_drawdown_pct=15.7,
            cagr_5y_pct=11.8,
            expense_ratio_pct=0.05,
        ),
        BenchmarkMetricModel(
            name="Nifty 500",
            description="Broader benchmark representing large, mid, and smaller listed companies.",
            category="INDEX",
            annual_return_pct=13.7,
            volatility_pct=18.1,
            sharpe_ratio=0.91,
            sortino_ratio=1.22,
            max_drawdown_pct=18.4,
            cagr_5y_pct=12.9,
            expense_ratio_pct=0.08,
        ),
        BenchmarkMetricModel(
            name="Momentum Basket",
            description="High-turnover momentum basket with stronger upside and deeper reversals.",
            category="FACTOR",
            annual_return_pct=18.1,
            volatility_pct=22.7,
            sharpe_ratio=1.02,
            sortino_ratio=1.39,
            max_drawdown_pct=24.2,
            cagr_5y_pct=16.4,
            expense_ratio_pct=0.42,
        ),
        BenchmarkMetricModel(
            name="AMC Multi Factor",
            description="Representative AMC-style diversified factor sleeve across quality, value, and momentum.",
            category="AMC_STYLE",
            annual_return_pct=14.8,
            volatility_pct=14.6,
            sharpe_ratio=1.11,
            sortino_ratio=1.51,
            max_drawdown_pct=12.9,
            cagr_5y_pct=13.9,
            expense_ratio_pct=0.34,
        ),
    ]

    projected_growth = []
    initial_amount = 500_000
    for year in range(0, 11):
        projected_growth.append(
            BenchmarkGrowthPointModel(
                year=year,
                values={
                    strategy.name: round(initial_amount * ((1 + ((strategy.annual_return_pct - strategy.expense_ratio_pct) / 100)) ** year), 2)
                    for strategy in strategies
                },
            )
        )

    return BenchmarkSummaryResponse(
        strategies=strategies,
        projected_growth=projected_growth,
        notes=[
            "These are placeholder benchmark summaries exposed through the backend contract.",
            "Production benchmarks should be computed from index and factor history using the same fee and tax framework as the strategy.",
        ],
    )
