from __future__ import annotations

import logging
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
    BenchmarkCompareRequest,
    BenchmarkCompareResponse,
    BenchmarkCompareStatsModel,
    BenchmarkSummaryResponse,
    BenchmarkRelativeStatsModel,
    BenchmarkSeriesPointModel,
    CrossAssetToneItemModel,
    CostBreakdownModel,
    CurvePointModel,
    GeneratePortfolioRequest,
    GeneratePortfolioResponse,
    MarketDashboardResponse,
    MarketFactorWeatherItemModel,
    MarketTrendBlockModel,
    PortfolioMetricsModel,
    PortfolioConstraintStatusModel,
    PortfolioFitSummaryModel,
    RiskContributionModel,
    RuntimeDescriptorModel,
    ScenarioShockModel,
    SectorRelativeStrengthModel,
    StandardMetricDefinitionModel,
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
from app.services.mandate import MandateConfig, derive_mandate_config
from app.services.market_rules import (
    financial_year_for_trade_date,
    resolve_capital_gains_tax_schedule,
    resolve_equity_fee_schedule,
)
from app.services.model_runtime import get_model_runtime_status
from app.services.news_signal import compute_stock_news_signals
from app.ml.ensemble_alpha.predict import get_ensemble_alpha_predictor
from app.ml.lightgbm_alpha.artifact_loader import get_lightgbm_model_status

logger = logging.getLogger(__name__)

RISK_FREE_RATE = 0.07
DEFAULT_BACKTEST_INVESTMENT = 1_000_000.0
DEFAULT_MODEL_FEATURE_LOOKBACK_DAYS = 450
DEFAULT_MODEL_MIN_TRADING_HISTORY = 253
DEFAULT_RULES_MIN_HISTORY = 90

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

RISK_PROFILE_GUIDANCE = {
    "ULTRA_LOW": {
        "label": "capital preservation",
        "target_beta": 0.8,
        "min_holdings": 6,
        "max_holdings": 10,
        "sector_cap_pct": 42.0,
    },
    "MODERATE": {
        "label": "moderate",
        "target_beta": 1.0,
        "min_holdings": 5,
        "max_holdings": 10,
        "sector_cap_pct": 28.0,
    },
    "HIGH": {
        "label": "growth",
        "target_beta": 1.2,
        "min_holdings": 8,
        "max_holdings": 14,
        "sector_cap_pct": 24.0,
    },
}


def _display_factor_name(name: str) -> str:
    return name.replace("_", " ")


def _factor_tilt_label(value: float) -> str:
    magnitude = abs(value)
    if magnitude < 0.15:
        return "near-neutral"
    if magnitude < 0.35:
        return "small tilt"
    return "strong tilt"


def _diversification_label(score: float) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "moderate"
    return "weak"


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def summarize_factor_profile(factor_exposures: dict[str, float]) -> str:
    ranked = sorted(factor_exposures.items(), key=lambda item: abs(item[1]), reverse=True)
    material = [(name, value) for name, value in ranked if abs(value) >= 0.1][:2]
    if not material:
        return "Factor profile is roughly market-like; all measured tilts are near-neutral."

    descriptions = []
    for name, value in material:
        direction = "positive" if value > 0 else "negative"
        descriptions.append(f"{_factor_tilt_label(value)} {direction} {_display_factor_name(name)}")
    return f"Factor profile is mostly market-like with {_join_list(descriptions)}."


def build_analysis_summary(
    *,
    total_holdings: int,
    target_risk_mode: str,
    current_beta: float,
    diversification_score: float,
    avg_corr: float,
    sector_weights: dict[str, float],
    factor_exposures: dict[str, float],
    current_weights: dict[str, float],
    actions: list[RebalanceActionModel],
) -> dict[str, object]:
    guidance = RISK_PROFILE_GUIDANCE[target_risk_mode]
    target_beta = float(guidance["target_beta"])
    sector_cap_pct = float(guidance["sector_cap_pct"])
    min_holdings = int(guidance["min_holdings"])
    max_holdings = int(guidance["max_holdings"])
    profile_label = str(guidance["label"])

    top_sector, top_sector_weight = ("", 0.0)
    if sector_weights:
        top_sector, top_sector_weight = max(sector_weights.items(), key=lambda item: item[1])

    max_name_weight = max(current_weights.values(), default=0.0)
    sector_count = len(sector_weights)
    diversification_label = _diversification_label(diversification_score)

    risk_messages: list[str] = []
    if current_beta >= target_beta + 0.2:
        risk_messages.append(
            f"Weighted beta {current_beta:.2f} is above the {profile_label} target of about {target_beta:.2f}, so the portfolio should be more volatile than the market."
        )
    elif current_beta <= target_beta - 0.15:
        risk_messages.append(
            f"Weighted beta {current_beta:.2f} is below the {profile_label} target of about {target_beta:.2f}, so the portfolio should be less volatile than the market."
        )
    else:
        risk_messages.append(
            f"Weighted beta {current_beta:.2f} is broadly in line with the {profile_label} target of about {target_beta:.2f}."
        )
    if total_holdings <= 4:
        risk_messages.append(f"That risk sits on only {total_holdings} stocks, which makes each position matter more.")
    risk_assessment = " ".join(risk_messages)

    diversification_assessment = (
        f"Diversification score {diversification_score:.0f}% is {diversification_label}. "
        f"In this model it combines sector breadth and average correlation, so {diversification_score:.0f}% means cross-sector diversification is helping, "
        f"but only {total_holdings} holdings across {sector_count} sectors still leaves the portfolio less diversified than a fuller {profile_label} basket."
    )

    if top_sector and top_sector_weight > sector_cap_pct:
        concentration_assessment = (
            f"{top_sector} is {top_sector_weight:.1f}% of the portfolio, well above the {profile_label} sector cap of about {sector_cap_pct:.0f}%. "
            f"A sector shock there could hit most of the portfolio at once."
        )
    elif top_sector and top_sector_weight >= sector_cap_pct - 5:
        concentration_assessment = (
            f"{top_sector} is the largest sector at {top_sector_weight:.1f}%, close to the {profile_label} cap of about {sector_cap_pct:.0f}%, so concentration is elevated."
        )
    else:
        concentration_assessment = (
            f"No sector is breaching the {profile_label} cap of about {sector_cap_pct:.0f}%; the largest sector is {top_sector or 'n/a'} at {top_sector_weight:.1f}%."
        )

    factor_assessment = summarize_factor_profile(factor_exposures)

    if avg_corr < 0.3:
        correlation_assessment = (
            f"Average pairwise correlation is {avg_corr:.2f}, which is low. Low correlations partially offset concentration because the holdings do not usually move together."
        )
    elif avg_corr < 0.6:
        correlation_assessment = (
            f"Average pairwise correlation is {avg_corr:.2f}, which is moderate. Diversification is helping, but the names still share a meaningful market/sector rhythm."
        )
    else:
        correlation_assessment = (
            f"Average pairwise correlation is {avg_corr:.2f}, which is high. The holdings are likely to move together in stress periods, so diversification is weak."
        )

    benchmark_flags: list[str] = []
    if current_beta > target_beta + 0.1:
        benchmark_flags.append("risk is above target")
    elif current_beta < target_beta - 0.1:
        benchmark_flags.append("risk is below target")
    else:
        benchmark_flags.append("beta is on target")
    if total_holdings < min_holdings:
        benchmark_flags.append(f"breadth is below the usual {min_holdings}-{max_holdings} holding range")
    elif total_holdings > max_holdings:
        benchmark_flags.append(f"breadth is above the usual {min_holdings}-{max_holdings} holding range")
    else:
        benchmark_flags.append("holding count is in range")
    if top_sector_weight > sector_cap_pct:
        benchmark_flags.append("sector concentration is above the normal cap")
    else:
        benchmark_flags.append("sector concentration is within cap")
    benchmark_assessment = (
        f"Against the {profile_label} benchmark used for this review (beta about {target_beta:.2f}, "
        f"{min_holdings}-{max_holdings} holdings, sector cap about {sector_cap_pct:.0f}%), {_join_list(benchmark_flags)}."
    )

    if total_holdings <= 4 or max_name_weight >= 35:
        idiosyncratic_risk_assessment = (
            f"Idiosyncratic risk is high because the portfolio holds only {total_holdings} names and the largest single position is {max_name_weight:.1f}%. "
            "A company-specific disappointment can materially move the whole portfolio."
        )
    else:
        idiosyncratic_risk_assessment = (
            f"Stock-specific risk is more contained: the portfolio has {total_holdings} names and the largest single position is {max_name_weight:.1f}%."
        )

    recommended_actions: list[str] = []
    if top_sector and top_sector_weight > sector_cap_pct:
        recommended_actions.append(
            f"Trim {top_sector} exposure by about {top_sector_weight - sector_cap_pct:.1f} percentage points to move back toward the {profile_label} sector cap."
        )

    missing_target_sectors = [
        sector for sector in RISK_MODE_TARGET_SECTORS[target_risk_mode].keys()
        if sector not in sector_weights
    ]
    if total_holdings < min_holdings or sector_count < 4:
        additional_names = max(1, min_holdings - total_holdings)
        add_sectors = missing_target_sectors[:2]
        if add_sectors:
            recommended_actions.append(
                f"Add at least {additional_names} more holdings across {', '.join(add_sectors)} to reduce stock-specific risk and broaden sector balance."
            )
        else:
            recommended_actions.append(
                f"Add at least {additional_names} more holdings outside the existing leaders to reduce stock-specific risk."
            )

    if current_beta > target_beta + 0.15:
        recommended_actions.append(
            f"Lower portfolio beta toward about {target_beta:.2f} by adding steadier sectors such as FMCG, Pharma, Telecom, Gold, or Liquid assets."
        )

    action_summaries = []
    for action in actions[:2]:
        drift = abs(action.target_weight - action.current_weight)
        verb = "Increase" if action.action == "BUY" else "Reduce"
        action_summaries.append(
            f"{verb} {action.symbol} by about {drift:.1f} percentage points toward a target weight of {action.target_weight:.1f}%."
        )
    recommended_actions.extend(action_summaries)

    deduped_actions: list[str] = []
    seen_actions: set[str] = set()
    for action_text in recommended_actions:
        if action_text in seen_actions:
            continue
        seen_actions.add(action_text)
        deduped_actions.append(action_text)

    if deduped_actions:
        rebalance_summary = (
            f"Rebalance is warranted: {len(actions)} holdings are outside the current {profile_label} drift bands."
            if actions
            else "Structural rebalance is warranted even though name-level drift bands have not been breached."
        )
    else:
        deduped_actions = ["Portfolio is within the current drift bands; no rebalance is required right now."]
        rebalance_summary = "Portfolio is within the current drift bands; no rebalance is required right now."

    concern_count = 0
    if current_beta > target_beta + 0.15:
        concern_count += 1
    if total_holdings < min_holdings or diversification_score < 55:
        concern_count += 1
    if top_sector_weight > sector_cap_pct:
        concern_count += 1
    if total_holdings <= 4 or max_name_weight >= 35:
        concern_count += 1

    if concern_count >= 3:
        health_label = "CAUTION"
        health_summary = (
            f"Portfolio health is under pressure: concentration and stock-specific risk are high for a {profile_label} portfolio, even though correlation relief is helping somewhat."
        )
    elif concern_count >= 1:
        health_label = "OKAY"
        health_summary = (
            f"Portfolio health is mixed: some risk controls are working, but breadth or concentration still needs attention for a {profile_label} profile."
        )
    else:
        health_label = "GOOD"
        health_summary = (
            f"Portfolio health looks solid for a {profile_label} profile: beta, diversification, and concentration are broadly aligned with the target guardrails."
        )

    return {
        "largest_sector": top_sector,
        "largest_sector_weight": round(top_sector_weight, 2),
        "health_label": health_label,
        "health_summary": health_summary,
        "risk_assessment": risk_assessment,
        "diversification_assessment": diversification_assessment,
        "concentration_assessment": concentration_assessment,
        "factor_assessment": factor_assessment,
        "correlation_assessment": correlation_assessment,
        "benchmark_assessment": benchmark_assessment,
        "idiosyncratic_risk_assessment": idiosyncratic_risk_assessment,
        "rebalance_summary": rebalance_summary,
        "recommended_actions": deduped_actions[:4],
    }


def build_runtime_descriptor(runtime_status: dict[str, object] | None = None) -> RuntimeDescriptorModel:
    runtime = runtime_status or get_model_runtime_status()
    return RuntimeDescriptorModel(
        variant=str(runtime.get("variant", "RULES")),  # type: ignore[arg-type]
        model_source=str(runtime.get("model_source", "RULES")),  # type: ignore[arg-type]
        active_mode=str(runtime.get("active_mode", "rules_only")),
        model_version=str(runtime.get("model_version", "rules")),
        artifact_classification=str(runtime.get("artifact_classification", "missing")),
        prediction_horizon_days=int(runtime.get("prediction_horizon_days", 21)),
    )


def build_standard_metrics(
    *,
    return_pct: float,
    volatility_pct: float,
    sharpe_ratio: float,
    diversification_score: float | None = None,
    correlation: float | None = None,
    beta: float | None = None,
) -> StandardMetricDefinitionModel:
    return StandardMetricDefinitionModel(
        return_pct=round(return_pct, 2),
        volatility_pct=round(volatility_pct, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        diversification_score=round(diversification_score, 2) if diversification_score is not None else None,
        correlation=round(correlation, 2) if correlation is not None else None,
        beta=round(beta, 2) if beta is not None else None,
    )


def build_portfolio_fit_summary(
    *,
    risk_level: str,
    diversification: str,
    concentration: str,
    next_action: str,
) -> PortfolioFitSummaryModel:
    return PortfolioFitSummaryModel(
        summary=f"Risk level: {risk_level}. Diversification: {diversification}. Concentration: {concentration}. Next action: {next_action}.",
        risk_level=risk_level,
        diversification=diversification,
        concentration=concentration,
        next_action=next_action,
    )


def estimate_turnover_pct(weights_pct: list[float], holding_period_days: int) -> float:
    if not weights_pct:
        return 0.0
    annual_rebalances = 252 / max(holding_period_days, 21)
    turnover = (sum(abs(weight - (100.0 / len(weights_pct))) for weight in weights_pct) / 2.0) * (annual_rebalances / 12.0)
    return round(min(250.0, max(8.0, turnover)), 1)


def compute_portfolio_risk_contributions(selected: list[tuple["Snapshot", float]]) -> tuple[list[RiskContributionModel], list[RiskContributionModel]]:
    if not selected:
        return [], []

    raw_position_scores = []
    sector_scores: dict[str, float] = defaultdict(float)
    for snapshot, weight in selected:
        raw_score = max(weight, 0.0) * max(snapshot.annual_volatility_pct, 1.0) * max(abs(snapshot.beta_proxy), 0.5)
        raw_position_scores.append((snapshot, weight, raw_score))
        sector_scores[snapshot.sector] += raw_score

    total_score = sum(score for _, _, score in raw_position_scores) or 1.0
    position_items = [
        RiskContributionModel(
            name=snapshot.symbol,
            weight_pct=round(weight, 2),
            contribution_pct=round((score / total_score) * 100.0, 2),
            detail=f"{snapshot.sector} · beta {snapshot.beta_proxy:.2f} · vol {snapshot.annual_volatility_pct:.1f}%",
        )
        for snapshot, weight, score in sorted(raw_position_scores, key=lambda item: item[2], reverse=True)
    ]

    sector_total = sum(sector_scores.values()) or 1.0
    sector_items = [
        RiskContributionModel(
            name=sector,
            weight_pct=round(sum(weight for snapshot, weight, _ in raw_position_scores if snapshot.sector == sector), 2),
            contribution_pct=round((score / sector_total) * 100.0, 2),
            detail="Aggregated from weighted volatility and beta contribution.",
        )
        for sector, score in sorted(sector_scores.items(), key=lambda item: item[1], reverse=True)
    ]
    return position_items, sector_items


def build_constraint_status(
    selected: list[tuple["Snapshot", float]],
    *,
    max_position_cap_pct: float,
    max_sector_cap_pct: float,
) -> PortfolioConstraintStatusModel:
    sector_weights: dict[str, float] = defaultdict(float)
    largest_name = ""
    largest_weight = 0.0
    for snapshot, weight in selected:
        sector_weights[snapshot.sector] += weight
        if weight > largest_weight:
            largest_name = snapshot.symbol
            largest_weight = weight
    largest_sector_name, largest_sector_weight = ("", 0.0)
    if sector_weights:
        largest_sector_name, largest_sector_weight = max(sector_weights.items(), key=lambda item: item[1])

    return PortfolioConstraintStatusModel(
        max_position_cap_pct=round(max_position_cap_pct, 2),
        max_sector_cap_pct=round(max_sector_cap_pct, 2),
        largest_position_pct=round(largest_weight, 2),
        largest_position_name=largest_name,
        largest_sector_weight_pct=round(largest_sector_weight, 2),
        largest_sector_name=largest_sector_name,
        near_position_cap=largest_weight >= max_position_cap_pct * 0.9,
        near_sector_cap=largest_sector_weight >= max_sector_cap_pct * 0.9,
    )


def infer_benchmark_name_for_mandate(mandate, holding_count: int) -> str:
    if mandate is None:
        return "Nifty 500 Proxy" if holding_count >= 12 else "Nifty 50 Proxy"
    if mandate.risk_attitude == "capital_preservation":
        return "Quality Factor"
    if mandate.risk_attitude == "growth":
        return "Momentum Factor"
    return "AMC Multi Factor" if holding_count >= 10 else "Nifty 500 Proxy"


def compute_active_share(weights: dict[str, float], benchmark_weights: dict[str, float]) -> float:
    symbols = set(weights) | set(benchmark_weights)
    return 50.0 * sum(abs((weights.get(symbol, 0.0) * 100.0) - (benchmark_weights.get(symbol, 0.0) * 100.0)) for symbol in symbols)


def compute_tracking_error_and_ir(strategy_returns: dict[date, float], benchmark_returns: dict[date, float]) -> tuple[float, float]:
    overlap_dates = [trade_date for trade_date in strategy_returns if trade_date in benchmark_returns]
    if len(overlap_dates) < 2:
        return 0.0, 0.0
    active_returns = [strategy_returns[trade_date] - benchmark_returns[trade_date] for trade_date in overlap_dates]
    mean_active = sum(active_returns) / len(active_returns)
    std_active = sqrt(sum((value - mean_active) ** 2 for value in active_returns) / max(len(active_returns) - 1, 1))
    tracking_error_pct = std_active * sqrt(252) * 100
    information_ratio = ((mean_active * 252) / max(std_active * sqrt(252), 1e-9)) if std_active > 0 else 0.0
    return round(tracking_error_pct, 2), round(information_ratio, 2)


def compute_capture_ratios(strategy_returns: dict[date, float], benchmark_returns: dict[date, float]) -> tuple[float, float]:
    upside_strategy: list[float] = []
    upside_benchmark: list[float] = []
    downside_strategy: list[float] = []
    downside_benchmark: list[float] = []
    for trade_date, benchmark_value in benchmark_returns.items():
        strategy_value = strategy_returns.get(trade_date)
        if strategy_value is None:
            continue
        if benchmark_value >= 0:
            upside_strategy.append(strategy_value)
            upside_benchmark.append(benchmark_value)
        else:
            downside_strategy.append(strategy_value)
            downside_benchmark.append(benchmark_value)

    def capture(numerator: list[float], denominator: list[float]) -> float:
        if not numerator or not denominator:
            return 0.0
        base = sum(denominator) / len(denominator)
        if abs(base) <= 1e-9:
            return 0.0
        return ((sum(numerator) / len(numerator)) / base) * 100.0

    downside_capture = capture(downside_strategy, downside_benchmark)
    upside_capture = capture(upside_strategy, upside_benchmark)
    return round(downside_capture, 2), round(upside_capture, 2)


def compute_drawdown_timing(return_series: dict[date, float]) -> tuple[int, int]:
    if not return_series:
        return 0, 0
    equity = 1.0
    peak = 1.0
    current_duration = 0
    longest_duration = 0
    recovery_days = 0
    max_recovery = 0
    in_drawdown = False
    for trade_date in sorted(return_series):
        equity *= 1.0 + return_series[trade_date]
        if equity >= peak:
            peak = equity
            if in_drawdown:
                max_recovery = max(max_recovery, recovery_days)
            in_drawdown = False
            recovery_days = 0
            current_duration = 0
        else:
            in_drawdown = True
            current_duration += 1
            recovery_days += 1
            longest_duration = max(longest_duration, current_duration)
    max_recovery = max(max_recovery, recovery_days)
    return longest_duration, max_recovery


def rolling_window_stats(return_series: dict[date, float], benchmark_returns: dict[date, float], window: int = 63) -> tuple[dict[date, float], dict[date, float]]:
    ordered_dates = [trade_date for trade_date in sorted(return_series) if trade_date in benchmark_returns]
    rolling_excess: dict[date, float] = {}
    rolling_sharpe: dict[date, float] = {}
    for index in range(window - 1, len(ordered_dates)):
        window_dates = ordered_dates[index - window + 1:index + 1]
        strat_window = [return_series[trade_date] for trade_date in window_dates]
        bench_window = [benchmark_returns[trade_date] for trade_date in window_dates]
        active_window = [left - right for left, right in zip(strat_window, bench_window)]
        rolling_excess[ordered_dates[index]] = round(sum(active_window) * 100.0, 2)
        avg = sum(strat_window) / len(strat_window)
        std = sqrt(sum((value - avg) ** 2 for value in strat_window) / max(len(strat_window) - 1, 1))
        rolling_sharpe[ordered_dates[index]] = round((((avg - (RISK_FREE_RATE / 252)) / max(std, 1e-9)) * sqrt(252)) if std > 0 else 0.0, 2)
    return rolling_excess, rolling_sharpe


def estimate_statutory_cost_and_tax_drag(
    annual_return_pct: float,
    *,
    weights: dict[str, float],
    snapshot_map: dict[str, "Snapshot"],
    turnover_pct: float,
    holding_period_days: int,
    trade_date: date,
    initial_investment: float = DEFAULT_BACKTEST_INVESTMENT,
) -> tuple[float, float]:
    normalized_weights = {
        symbol: float(weight)
        for symbol, weight in weights.items()
        if weight > 0 and symbol in snapshot_map
    }
    total_weight = sum(normalized_weights.values()) or 1.0
    gross_executed_notional = initial_investment * max(turnover_pct, 0.0) / 100.0
    cost_total = 0.0
    for symbol, weight in normalized_weights.items():
        snapshot = snapshot_map[symbol]
        symbol_notional = gross_executed_notional * (weight / total_weight)
        if symbol_notional <= 0:
            continue
        buy_notional = symbol_notional / 2.0
        sell_notional = symbol_notional / 2.0
        buy_costs = calculate_trade_costs(
            amount=buy_notional,
            trade_date=trade_date,
            is_buy=True,
            avg_traded_value=snapshot.avg_traded_value,
            annual_volatility_pct=snapshot.annual_volatility_pct,
        )
        sell_costs = calculate_trade_costs(
            amount=sell_notional,
            trade_date=trade_date,
            is_buy=False,
            avg_traded_value=snapshot.avg_traded_value,
            annual_volatility_pct=snapshot.annual_volatility_pct,
        )
        cost_total += buy_costs["total_costs"] + sell_costs["total_costs"]

    cost_drag_pct = (cost_total / max(initial_investment, 1.0)) * 100.0
    realized_gain_amount = initial_investment * max(annual_return_pct, 0.0) / 100.0
    realized_gain_amount *= min(1.0, max(turnover_pct, 0.0) / 100.0)

    tax_schedule = resolve_capital_gains_tax_schedule(trade_date)
    if holding_period_days >= 365:
        taxable_gain = max(0.0, realized_gain_amount - tax_schedule.ltcg_exemption)
        base_tax = taxable_gain * tax_schedule.ltcg_rate
    else:
        taxable_gain = max(0.0, realized_gain_amount)
        base_tax = taxable_gain * tax_schedule.stcg_rate
    tax_total = base_tax + (base_tax * tax_schedule.cess_rate)
    tax_drag_pct = (tax_total / max(initial_investment, 1.0)) * 100.0

    return (
        round(annual_return_pct - cost_drag_pct, 2),
        round(annual_return_pct - cost_drag_pct - tax_drag_pct, 2),
    )


def build_generate_scenario_tests(selected: list[tuple["Snapshot", float]], weighted_beta: float) -> list[ScenarioShockModel]:
    sector_weights: dict[str, float] = defaultdict(float)
    for snapshot, weight in selected:
        sector_weights[snapshot.sector] += weight

    crude_sensitivity = (sector_weights.get("Energy", 0.0) + 0.5 * sector_weights.get("Auto", 0.0)) / 100.0
    rates_sensitivity = (sector_weights.get("Banking", 0.0) + sector_weights.get("Finance", 0.0) + 0.4 * sector_weights.get("Real Estate", 0.0)) / 100.0
    banking_sensitivity = (sector_weights.get("Banking", 0.0) + sector_weights.get("Finance", 0.0)) / 100.0

    return [
        ScenarioShockModel(
            name="Market -10%",
            pnl_pct=round(-10.0 * max(weighted_beta, 0.6), 2),
            commentary="Broad market selloff scaled by weighted beta.",
        ),
        ScenarioShockModel(
            name="Rate shock",
            pnl_pct=round(-(2.0 + 6.0 * rates_sensitivity), 2),
            commentary="Higher rates typically pressure financials and duration-sensitive sectors.",
        ),
        ScenarioShockModel(
            name="Crude shock",
            pnl_pct=round(-1.5 - (7.0 * crude_sensitivity), 2),
            commentary="Crude-sensitive sectors and INR pass-through names take the first hit.",
        ),
        ScenarioShockModel(
            name="Banking shock",
            pnl_pct=round(-2.0 - (8.0 * banking_sensitivity), 2),
            commentary="Concentrated financial exposure increases downside if credit spreads widen.",
        ),
    ]


def build_generate_portfolio_fit_summary(
    *,
    metrics: PortfolioMetricsModel,
    constraints: PortfolioConstraintStatusModel,
    residual_cash: float,
) -> PortfolioFitSummaryModel:
    risk_level = (
        "high"
        if metrics.beta >= 1.15 or metrics.estimated_volatility_pct >= 20
        else "balanced"
        if metrics.beta >= 0.9
        else "defensive"
    )
    diversification = (
        "strong"
        if metrics.diversification_score >= 75
        else "moderate"
        if metrics.diversification_score >= 55
        else "narrow"
    )
    concentration = (
        f"largest position {constraints.largest_position_name} at {constraints.largest_position_pct:.1f}% and {constraints.largest_sector_name} at {constraints.largest_sector_weight_pct:.1f}%"
        if constraints.largest_position_name
        else "no material concentration flags"
    )
    if residual_cash > 0:
        next_action = f"Keep residual cash of Rs {residual_cash:,.0f} ready for staggered deployment or a better entry."
    elif constraints.near_position_cap or constraints.near_sector_cap:
        next_action = "Monitor cap usage because the book is already leaning into its concentration guardrails."
    else:
        next_action = "Book is deployable now; review only if factor leadership or breadth deteriorates."
    return build_portfolio_fit_summary(
        risk_level=risk_level,
        diversification=diversification,
        concentration=concentration,
        next_action=next_action,
    )


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
    news_risk_score: float = 0.0
    news_opportunity_score: float = 0.0
    news_sentiment: float = 0.0
    news_impact: float = 0.0
    news_explanation: str = ""


@dataclass(frozen=True)
class BarRecord:
    trade_date: date
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    total_traded_value: float


def predict_ensemble_for_snapshots(
    db: Session,
    snapshots: list[Snapshot],
    as_of_date: date,
) -> tuple[dict[str, object], dict[str, object]]:
    predictor = get_ensemble_alpha_predictor()

    equity_snapshots = [snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY"]
    if not equity_snapshots:
        return {}, {"available": False, "reason": "no_equity_snapshots"}

    reloaded_symbols = sorted(
        snapshot.symbol
        for snapshot in equity_snapshots
        if len(snapshot.adjusted_closes) < DEFAULT_MODEL_MIN_TRADING_HISTORY
    )
    inference_snapshots = equity_snapshots
    if reloaded_symbols:
        refreshed_snapshots = load_snapshots(
            db,
            as_of_date=as_of_date,
            symbols=[snapshot.symbol for snapshot in equity_snapshots],
            lookback_days=DEFAULT_MODEL_FEATURE_LOOKBACK_DAYS,
            min_history=DEFAULT_MODEL_MIN_TRADING_HISTORY,
        )
        refreshed_map = {
            snapshot.symbol: snapshot
            for snapshot in refreshed_snapshots
            if snapshot.instrument_type == "EQUITY"
        }
        inference_snapshots = []
        for snapshot in equity_snapshots:
            refreshed = refreshed_map.get(snapshot.symbol)
            if refreshed is not None:
                inference_snapshots.append(refreshed)
            elif len(snapshot.adjusted_closes) >= DEFAULT_MODEL_MIN_TRADING_HISTORY:
                inference_snapshots.append(snapshot)
    if not inference_snapshots:
        return {}, {
            "available": False,
            "reason": "insufficient_history_for_ensemble",
            "history_refreshed_symbols": reloaded_symbols,
            "insufficient_history_symbols": reloaded_symbols,
        }

    predictions_by_symbol, model_info = predictor.predict(db, inference_snapshots, as_of_date)
    enriched_model_info = dict(model_info)
    if reloaded_symbols:
        enriched_model_info["history_refreshed_symbols"] = reloaded_symbols
    missing_after_refresh = sorted(
        symbol for symbol in reloaded_symbols if symbol not in {snapshot.symbol for snapshot in inference_snapshots}
    )
    if missing_after_refresh:
        enriched_model_info["insufficient_history_symbols"] = missing_after_refresh
    return predictions_by_symbol, enriched_model_info


def resolve_mandate_history_requirements(
    mandate_config: MandateConfig,
    model_variant: ModelVariant,
) -> tuple[int, int]:
    if model_variant == "LIGHTGBM_HYBRID":
        return (
            max(mandate_config.decision_lookback_days, mandate_config.model_feature_lookback_days),
            mandate_config.model_min_history_days,
        )
    return (
        mandate_config.decision_lookback_days,
        max(DEFAULT_RULES_MIN_HISTORY, mandate_config.decision_lookback_days // 2),
    )


def mandate_holding_period_scale(mandate_config: MandateConfig) -> float:
    return min(1.2, max(0.75, mandate_config.holding_period_days / 42.0))


def allocate_whole_shares_for_capital(
    selected: list[tuple[Snapshot, float]],
    capital_amount: float,
) -> tuple[dict[str, dict[str, float | int]], float]:
    plan: dict[str, dict[str, float | int]] = {}
    total_allocated = 0.0

    for snapshot, weight in selected:
        target_amount = max(0.0, capital_amount * (weight / 100.0))
        latest_price = max(float(snapshot.latest_price), 0.01)
        shares = int(target_amount // latest_price)
        allocated_amount = round(shares * latest_price, 2)
        plan[snapshot.symbol] = {
            "target_amount": round(target_amount, 2),
            "shares": shares,
            "amount": allocated_amount,
            "latest_price": round(latest_price, 2),
        }
        total_allocated += allocated_amount

    remaining_cash = round(max(0.0, capital_amount - total_allocated), 2)

    while remaining_cash > 0:
        candidates: list[tuple[float, float, float, int, str]] = []
        for selection_rank, (snapshot, _) in enumerate(selected):
            latest_price = max(float(snapshot.latest_price), 0.01)
            if latest_price > remaining_cash + 1e-9:
                continue
            entry = plan[snapshot.symbol]
            current_amount = float(entry["amount"])
            target_amount = float(entry["target_amount"])
            target_gap = target_amount - current_amount
            expected_return = float(snapshot.ml_pred_annual_return or 0.0)
            candidates.append((target_gap, expected_return, -latest_price, -selection_rank, snapshot.symbol))

        if not candidates:
            break

        _, _, _, _, chosen_symbol = max(candidates)
        chosen_entry = plan[chosen_symbol]
        chosen_price = float(chosen_entry["latest_price"])
        chosen_entry["shares"] = int(chosen_entry["shares"]) + 1
        chosen_entry["amount"] = round(float(chosen_entry["amount"]) + chosen_price, 2)
        remaining_cash = round(max(0.0, remaining_cash - chosen_price), 2)

    return plan, remaining_cash


def generate_portfolio(db: Session, payload: GeneratePortfolioRequest) -> GeneratePortfolioResponse:
    as_of_date = payload.as_of_date or get_effective_trade_date(db)
    runtime_status = get_model_runtime_status()
    mandate_config = derive_mandate_config(payload.mandate)
    history_lookback_days, min_history = resolve_mandate_history_requirements(mandate_config, payload.model_variant)
    snapshots = load_snapshots(
        db,
        as_of_date=as_of_date,
        lookback_days=history_lookback_days,
        min_history=min_history,
    )
    selected = select_portfolio_candidates_for_mandate(
        db,
        as_of_date,
        payload.mandate,
        snapshots,
        mandate_config,
        model_variant=payload.model_variant,
    )
    if not selected:
        raise ValueError(
            "No securities cleared the mandate filters. Loosen the position count, horizon, or small-cap setting."
        )

    weighted_stats = build_weighted_statistics(selected)
    factor_exposures = compute_factor_exposures([(snapshot, weight / 100.0) for snapshot, weight in selected])
    position_risk_contributions, sector_risk_contributions = compute_portfolio_risk_contributions(selected)
    constraint_status = build_constraint_status(
        selected,
        max_position_cap_pct=RISK_MODEL_CONFIG[mandate_config.risk_mode]["max_weight"] * 100.0,
        max_sector_cap_pct=RISK_MODEL_CONFIG[mandate_config.risk_mode]["sector_cap"] * 100.0,
    )
    turnover_estimate_pct = estimate_turnover_pct([weight for _, weight in selected], mandate_config.holding_period_days)
    scenario_tests = build_generate_scenario_tests(selected, weighted_stats.beta)
    adjusted_names = sum(1 for snapshot, _ in selected if snapshot.corporate_action_count > 0)
    average_news_risk = sum(snapshot.news_risk_score * (weight / 100.0) for snapshot, weight in selected)
    average_news_opportunity = sum(snapshot.news_opportunity_score * (weight / 100.0) for snapshot, weight in selected)
    notes = [
        f"Portfolio built from {len(selected)} instruments using prices through {as_of_date.isoformat()}.",
        (
            f"Mandate horizon {payload.mandate.investment_horizon_weeks} weeks maps to a {mandate_config.decision_lookback_days}-day decision window "
            f"and {mandate_config.holding_period_days}-day expected holding period."
        ),
        (
            f"Universe filters applied: target {payload.mandate.preferred_num_positions} positions, "
            f"small caps {'allowed' if payload.mandate.allow_small_caps else 'excluded'}."
        ),
        (
            f"Risk profile {payload.mandate.risk_attitude.replace('_', ' ')} uses a volatility screen of "
            f"{mandate_config.max_annual_volatility_pct:.1f}% and death-risk screen of {mandate_config.max_death_risk:.2f}."
        ),
        "Expected returns combine ensemble forecasts, factor context, and news semantics aligned to the chosen horizon.",
        "Weights are produced by a long-only allocator over a shrinkage covariance matrix estimated from aligned total-return series.",
        f"Weighted factor exposures: momentum {factor_exposures['momentum']:+.2f}, quality {factor_exposures['quality']:+.2f}, low_vol {factor_exposures['low_vol']:+.2f}.",
        f"News overlay: weighted risk {average_news_risk:.2f}, opportunity {average_news_opportunity:.2f}.",
        (
            f"Corporate-action-adjusted histories were used for {adjusted_names} selected instruments."
            if adjusted_names
            else "No corporate actions were loaded for the selected instruments, so adjusted and raw close histories currently match."
        ),
    ]
    if payload.model_variant == "LIGHTGBM_HYBRID":
        notes.append(
            f"Ensemble feature history is loaded from up to {history_lookback_days} calendar days with a {min_history}-session minimum, so mandate horizon shapes decisions without truncating model inputs."
        )

    used_ml_count = sum(1 for snapshot, _ in selected if snapshot.expected_return_source == "ENSEMBLE")
    model_source = "ENSEMBLE" if used_ml_count > 0 else "RULES"
    model_version = next((snapshot.model_version for snapshot, _ in selected if snapshot.expected_return_source == "ENSEMBLE"), "rules")
    prediction_horizon_days = next((snapshot.prediction_horizon_days for snapshot, _ in selected if snapshot.expected_return_source == "ENSEMBLE"), 21)

    if payload.model_variant == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            notes.append(
                f"Ensemble runtime used for {used_ml_count} equities and directly drove expected-return ranking. Model version: {model_version}."
            )
        else:
            raise ValueError("Ensemble runtime was requested, but no valid ensemble predictions were produced.")

    run = GeneratedPortfolioRun(
        risk_mode=payload.mandate.risk_attitude.upper(),
        investment_amount=Decimal(str(round(payload.capital_amount, 2))),
        as_of_date=as_of_date,
        metrics_json=weighted_stats.model_dump(),
        notes="\n".join(notes),
    )
    db.add(run)
    db.flush()

    whole_share_plan, residual_cash = allocate_whole_shares_for_capital(selected, payload.capital_amount)
    deployment_efficiency_pct = round(((payload.capital_amount - residual_cash) / payload.capital_amount) * 100.0, 2) if payload.capital_amount else 0.0
    if residual_cash > 0:
        notes.append(
            f"Whole-share sizing deployed Rs {payload.capital_amount - residual_cash:,.2f} with Rs {residual_cash:,.2f} left as residual cash."
        )

    allocations: list[AllocationModel] = []
    for snapshot, weight in selected:
        rationale = build_rationale_for_mandate(snapshot, payload.mandate, mandate_config)
        whole_share_entry = whole_share_plan.get(snapshot.symbol, {})
        db.add(
            GeneratedPortfolioAllocation(
                portfolio_run_id=run.id,
                symbol=snapshot.symbol,
                sector=snapshot.sector,
                weight=Decimal(str(round(weight, 4))),
                rationale=rationale,
            )
        )
        drivers = list(snapshot.top_model_drivers)
        death_risk_val = None
        lstm_val = None
        for d in drivers:
            if d.startswith("death_risk="):
                try: death_risk_val = float(d.split("=")[1])
                except: pass
            if d.startswith("lstm="):
                try: lstm_val = float(d.split("=")[1])
                except: pass

        allocations.append(
            AllocationModel(
                symbol=snapshot.symbol,
                name=snapshot.name,
                sector=snapshot.sector,
                latest_price=round(float(snapshot.latest_price), 2),
                weight=round(weight, 2),
                recommended_shares=int(whole_share_entry.get("shares", 0)),
                recommended_amount=round(float(whole_share_entry.get("amount", 0.0)), 2),
                shares=int(whole_share_entry.get("shares", 0)),
                amount=round(float(whole_share_entry.get("amount", 0.0)), 2),
                rationale=rationale,
                top_model_drivers=drivers,
                ml_pred_21d_return=round(float(snapshot.ml_pred_21d_return), 4) if snapshot.ml_pred_21d_return is not None else None,
                ml_pred_annual_return=round(float(snapshot.ml_pred_annual_return), 4) if snapshot.ml_pred_annual_return is not None else None,
                death_risk=death_risk_val,
                lstm_signal=lstm_val,
                news_risk_score=round(snapshot.news_risk_score, 4),
                news_opportunity_score=round(snapshot.news_opportunity_score, 4),
                news_sentiment=round(snapshot.news_sentiment, 4),
                news_impact=round(snapshot.news_impact, 4),
                news_explanation=snapshot.news_explanation,
            )
        )

    weights_map = {snapshot.symbol: weight / 100.0 for snapshot, weight in selected}
    benchmark_name = infer_benchmark_name_for_mandate(payload.mandate, len(selected))
    if benchmark_name == "Momentum Factor":
        benchmark_weights = build_factor_portfolio(snapshots, factor_key="momentum", count=max(8, len(selected)), sector_cap=0.24)
    elif benchmark_name == "Quality Factor":
        benchmark_weights = build_factor_portfolio(snapshots, factor_key="quality", count=max(8, len(selected)), sector_cap=0.24)
    elif benchmark_name == "AMC Multi Factor":
        benchmark_weights = build_multifactor_portfolio(snapshots, count=max(10, len(selected)), sector_cap=0.22)
    elif benchmark_name == "Nifty 500 Proxy":
        benchmark_weights = build_nifty500_proxy_portfolio(snapshots)
    else:
        benchmark_weights = build_nifty50_proxy_portfolio(snapshots)
    strategy_returns = aggregate_portfolio_returns({snapshot.symbol: snapshot for snapshot, _ in selected}, weights_map)
    benchmark_returns = aggregate_portfolio_returns({snapshot.symbol: snapshot for snapshot in snapshots}, benchmark_weights)
    tracking_error_pct, information_ratio = compute_tracking_error_and_ir(strategy_returns, benchmark_returns)
    benchmark_metrics = summarize_return_series(benchmark_returns)
    benchmark_relative = BenchmarkRelativeStatsModel(
        benchmark_name=benchmark_name,
        active_share_pct=round(compute_active_share(weights_map, benchmark_weights), 2),
        tracking_error_pct=tracking_error_pct,
        ex_ante_alpha_pct=round(weighted_stats.estimated_return_pct - benchmark_metrics["annual_return_pct"], 2),
        information_ratio=information_ratio,
    )
    standard_metrics = build_standard_metrics(
        return_pct=weighted_stats.estimated_return_pct,
        volatility_pct=weighted_stats.estimated_volatility_pct,
        sharpe_ratio=(weighted_stats.estimated_return_pct - (RISK_FREE_RATE * 100.0)) / max(weighted_stats.estimated_volatility_pct, 1.0),
        diversification_score=weighted_stats.diversification_score,
        correlation=average_pairwise_correlation([snapshot for snapshot, _ in selected]),
        beta=weighted_stats.beta,
    )
    portfolio_fit_summary = build_generate_portfolio_fit_summary(
        metrics=weighted_stats,
        constraints=constraint_status,
        residual_cash=residual_cash,
    )

    db.commit()
    return GeneratePortfolioResponse(
        model_variant=payload.model_variant,
        model_source=model_source,  # type: ignore[arg-type]
        model_version=model_version,
        prediction_horizon_days=prediction_horizon_days,
        capital_amount=payload.capital_amount,
        mandate=payload.mandate,
        lookback_window_days=mandate_config.decision_lookback_days,
        expected_holding_period_days=mandate_config.holding_period_days,
        allocations=allocations,
        metrics=weighted_stats,
        standard_metrics=standard_metrics,
        factor_exposures={key: round(value, 2) for key, value in factor_exposures.items()},
        position_risk_contributions=position_risk_contributions[:8],
        sector_risk_contributions=sector_risk_contributions,
        constraints=constraint_status,
        turnover_estimate_pct=turnover_estimate_pct,
        deployment_efficiency_pct=deployment_efficiency_pct,
        residual_cash=round(residual_cash, 2),
        scenario_tests=scenario_tests,
        benchmark_relative=benchmark_relative,
        portfolio_fit_summary=portfolio_fit_summary,
        runtime=build_runtime_descriptor(runtime_status),
        regime_warning="Current bear regime signals negative expected returns. Consider waiting for confirmation of trend reversal before deploying full capital." if weighted_stats.estimated_return_pct < 0 or ((weighted_stats.estimated_return_pct - 7) / max(weighted_stats.estimated_volatility_pct, 1)) < 0 else None,
        notes=notes,
    )


def analyze_portfolio(db: Session, payload: AnalyzePortfolioRequest) -> AnalyzePortfolioResponse:
    ml_status = get_lightgbm_model_status()
    runtime_status = get_model_runtime_status()
    if payload.model_variant is None:
        model_variant_applied: ModelVariant = "LIGHTGBM_HYBRID" if ml_status.get("available") else "RULES"
    else:
        model_variant_applied = payload.model_variant
        if model_variant_applied == "LIGHTGBM_HYBRID" and not ml_status.get("available"):
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
    current_weights = {snapshot.symbol: (value / total_value) * 100 for _, snapshot, value in priced_holdings}
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
    analysis_summary = build_analysis_summary(
        total_holdings=len(payload.holdings),
        target_risk_mode=payload.target_risk_mode,
        current_beta=current_beta,
        diversification_score=diversification_score,
        avg_corr=avg_corr,
        sector_weights=sector_weights,
        factor_exposures=factor_exposures,
        current_weights=current_weights,
        actions=actions,
    )
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
    notes.extend(
        [
            str(analysis_summary["health_summary"]),
            str(analysis_summary["risk_assessment"]),
            str(analysis_summary["diversification_assessment"]),
            str(analysis_summary["concentration_assessment"]),
            str(analysis_summary["factor_assessment"]),
            str(analysis_summary["correlation_assessment"]),
            str(analysis_summary["benchmark_assessment"]),
            str(analysis_summary["idiosyncratic_risk_assessment"]),
            str(analysis_summary["rebalance_summary"]),
        ]
    )
    if missing_symbols:
        notes.append(f"No market data found yet for: {', '.join(sorted(set(missing_symbols)))}.")

    used_ml_count = sum(1 for snapshot, _ in target_portfolio if snapshot.expected_return_source == "ENSEMBLE")

    model_source_note = ""
    if model_variant_applied == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            model_source_note = f"LightGBM hybrid applied to {used_ml_count} equities; allocator used blended ML+rules expected returns (75/25)."
        else:
            model_source_note = "LightGBM hybrid requested, but no valid equity predictions were produced; using rules expected returns."
    if model_source_note:
        notes.append(model_source_note)

    ml_predictions: dict[str, float] = {}
    top_model_drivers_by_symbol: dict[str, list[str]] = {}
    holdings_inference_note: str | None = None
    if model_variant_applied == "LIGHTGBM_HYBRID" and snapshots:
        try:
            pred_map, model_info = predict_ensemble_for_snapshots(db, snapshots, as_of_date)
            for sym, pred in pred_map.items():
                ml_predictions[sym] = pred.pred_annual_return
            for snapshot in snapshots:
                if snapshot.symbol in pred_map and snapshot.instrument_type == "EQUITY":
                    snapshot.expected_return_source = "ENSEMBLE"
                    snapshot.top_model_drivers = list(pred_map[snapshot.symbol].top_drivers)
                    snapshot.ml_pred_annual_return = float(pred_map[snapshot.symbol].pred_annual_return)
                    snapshot.ml_pred_21d_return = float(pred_map[snapshot.symbol].pred_21d_return)
                    snapshot.model_version = str(model_info.get("model_version", "unknown"))
                    snapshot.prediction_horizon_days = int(model_info.get("prediction_horizon_days", 21))
                    top_model_drivers_by_symbol[snapshot.symbol] = list(snapshot.top_model_drivers)
        except Exception:
            logger.exception("Analyze portfolio holdings inference failed; falling back to rules-only overlays.")
            holdings_inference_note = "Holding-level ensemble inference failed during analysis, so holdings overlays fell back to rules."

    if holdings_inference_note:
        notes.append(holdings_inference_note)

    return AnalyzePortfolioResponse(
        total_holdings=len(payload.holdings),
        portfolio_value=round(total_value, 2),
        current_beta=current_beta,
        diversification_score=diversification_score,
        avg_pairwise_correlation=round(avg_corr, 2),
        sector_weights=sector_weights,
        largest_sector=str(analysis_summary["largest_sector"]),
        largest_sector_weight=float(analysis_summary["largest_sector_weight"]),
        factor_exposures={key: round(value, 2) for key, value in factor_exposures.items()},
        correlation_risk=correlation_risk,
        actions=actions,
        health_label=str(analysis_summary["health_label"]),
        health_summary=str(analysis_summary["health_summary"]),
        risk_assessment=str(analysis_summary["risk_assessment"]),
        diversification_assessment=str(analysis_summary["diversification_assessment"]),
        concentration_assessment=str(analysis_summary["concentration_assessment"]),
        factor_assessment=str(analysis_summary["factor_assessment"]),
        correlation_assessment=str(analysis_summary["correlation_assessment"]),
        benchmark_assessment=str(analysis_summary["benchmark_assessment"]),
        idiosyncratic_risk_assessment=str(analysis_summary["idiosyncratic_risk_assessment"]),
        rebalance_summary=str(analysis_summary["rebalance_summary"]),
        portfolio_fit_summary=build_portfolio_fit_summary(
            risk_level=str(analysis_summary["risk_assessment"]),
            diversification=str(analysis_summary["diversification_assessment"]),
            concentration=str(analysis_summary["concentration_assessment"]),
            next_action=(analysis_summary["recommended_actions"][0] if analysis_summary["recommended_actions"] else str(analysis_summary["rebalance_summary"])),
        ),
        standard_metrics=build_standard_metrics(
            return_pct=0.0,
            volatility_pct=0.0,
            sharpe_ratio=0.0,
            diversification_score=diversification_score,
            correlation=avg_corr,
            beta=current_beta,
        ),
        recommended_actions=[str(item) for item in analysis_summary["recommended_actions"]],
        model_variant_applied=model_variant_applied,
        model_source="ENSEMBLE" if ml_predictions else "RULES",
        active_mode=str(runtime_status.get("active_mode", "rules_only")),
        model_version=str(runtime_status.get("model_version", "rules")),
        artifact_classification=str(runtime_status.get("artifact_classification", "missing")),
        prediction_horizon_days=int(runtime_status.get("prediction_horizon_days", 21)),
        runtime=build_runtime_descriptor(runtime_status),
        ml_predictions=ml_predictions,
        top_model_drivers_by_symbol=top_model_drivers_by_symbol,
        holding_period_days_recommended=int(runtime_status.get("prediction_horizon_days", 21)),
        holding_period_reason=(
            "Review holdings on the active model horizon when ML scores are available."
            if ml_predictions
            else "Review holdings monthly; this analysis is currently using the rules-based fallback."
        ),
        notes=notes,
    )


def run_backtest(db: Session, payload: BacktestRequest) -> BacktestResultResponse:
    ml_status = get_lightgbm_model_status()
    model_variant_applied = payload.model_variant
    if model_variant_applied == "LIGHTGBM_HYBRID" and not ml_status.get("available"):
        model_variant_applied = "RULES"

    selection_date = get_effective_trade_date(db, payload.start_date)
    if payload.mandate is not None:
        mandate_config = derive_mandate_config(payload.mandate)
        history_lookback_days, min_history = resolve_mandate_history_requirements(mandate_config, model_variant_applied)
        snapshots = load_snapshots(
            db,
            as_of_date=selection_date,
            lookback_days=history_lookback_days,
            min_history=min_history,
        )
        model_portfolio = select_portfolio_candidates_for_mandate(
            db,
            selection_date,
            payload.mandate,
            snapshots,
            mandate_config,
            model_variant=model_variant_applied,
        )
        runtime_risk_mode = {
            "capital_preservation": "ULTRA_LOW",
            "balanced": "MODERATE",
            "growth": "HIGH",
        }[payload.mandate.risk_attitude]
        initial_investment = payload.capital_amount or DEFAULT_BACKTEST_INVESTMENT
    else:
        if payload.risk_mode is None:
            raise ValueError("Backtest requires either a mandate or a legacy risk_mode.")
        ml_min_history = 252 if model_variant_applied == "LIGHTGBM_HYBRID" else 126
        snapshots = load_snapshots(
            db,
            as_of_date=selection_date,
            symbols=RISK_MODE_UNIVERSES[payload.risk_mode],
            min_history=ml_min_history,
        )
        if len(snapshots) < 4:
            snapshots = load_snapshots(db, as_of_date=selection_date, min_history=90)
        model_portfolio = select_portfolio_candidates(db, selection_date, payload.risk_mode, snapshots, model_variant=model_variant_applied)
        runtime_risk_mode = payload.risk_mode
        initial_investment = payload.capital_amount or DEFAULT_BACKTEST_INVESTMENT

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
    turnover_state = {
        "gross_executed_notional": 0.0,
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
        initial_investment=initial_investment,
        costs=costs,
        snapshot_by_symbol=snapshot_by_symbol,
    )
    if not position_state:
        raise ValueError("Selected instruments do not have usable prices on the requested backtest start date.")
    equity_curve: list[CurvePointModel] = []
    portfolio_returns: list[float] = []
    prev_value = initial_investment
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
            exit_fill, _ = determine_exit_fill(bar, state, runtime_risk_mode, payload.stop_loss_pct, payload.take_profit_pct)
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
                turnover_state["gross_executed_notional"] += proceeds
                state["peak_price"] = 0.0
                state["cooldown_until"] = trade_date + timedelta(days=RISK_MODEL_CONFIG[runtime_risk_mode]["cooldown_days"])
                total_trades += 1

        portfolio_value = current_portfolio_value(position_state, bar_matrix, trade_date)

        if index > 0 and index % rebalance_interval == 0 and payload.rebalance_frequency != "NONE":
            total_trades += rebalance_positions(
                position_state,
                bar_matrix,
                weights,
                trade_date,
                portfolio_value,
                costs,
                taxes,
                tax_buckets,
                runtime_risk_mode,
                turnover_state,
            )
            portfolio_value = current_portfolio_value(position_state, bar_matrix, trade_date)

        if index > 0:
            portfolio_returns.append((portfolio_value - prev_value) / max(prev_value, 1))
        prev_value = portfolio_value

        benchmark_value = DEFAULT_BACKTEST_INVESTMENT
        benchmark_value = initial_investment
        if benchmark_first_price and trade_date in benchmark_series:
            benchmark_price = benchmark_series[trade_date].close_price
            benchmark_value = initial_investment * (benchmark_price / benchmark_first_price)

        equity_curve.append(
            CurvePointModel(
                date=trade_date,
                portfolio_value=round(portfolio_value, 2),
                benchmark_value=round(benchmark_value, 2),
            )
        )

    finalize_tax_buckets(taxes, tax_buckets)

    metrics = build_backtest_metrics(
        equity_curve,
        portfolio_returns,
        costs,
        taxes,
        total_trades,
        turnover_state["gross_executed_notional"],
    )
    run_id = f"bt-{uuid4()}"
    fee_schedule = resolve_equity_fee_schedule(payload.end_date)
    tax_schedule = resolve_capital_gains_tax_schedule(payload.end_date)
    adjusted_names = sum(1 for snapshot in snapshot_by_symbol.values() if snapshot.corporate_action_count > 0)
    notes = [
        f"Historical replay used {len(weights)} data-backed instruments between {payload.start_date.isoformat()} and {payload.end_date.isoformat()}.",
        "Stop-loss and take-profit were evaluated on adjusted OHLC bars with gap-aware fills at the open when a threshold was crossed overnight.",
        (
            f"Rebalance policy used a {RISK_MODEL_CONFIG[runtime_risk_mode]['drift_threshold'] * 100:.1f}% drift threshold and "
            f"{payload.rebalance_frequency.lower()} review cycle for {runtime_risk_mode.lower()} mode."
        ),
        f"Equity fees used the {fee_schedule.effective_from.isoformat()} rule set: {fee_schedule.notes}",
        f"Capital gains used the {tax_schedule.effective_from.isoformat()} rule set with FY-wise LTCG exemption handling: {tax_schedule.notes}",
        (
            f"Corporate actions were applied to {adjusted_names} portfolio instruments, including split/bonus price adjustment and dividend cash credits."
            if adjusted_names
            else "No corporate actions were loaded for the portfolio instruments in this backtest window."
        ),
        "Turnover now reflects executed gross trade notional relative to starting capital instead of a trades-based heuristic.",
    ]
    if payload.mandate is not None:
        notes.insert(
            1,
            (
                f"Mandate replay used horizon {payload.mandate.investment_horizon_weeks}, "
                f"{payload.mandate.preferred_num_positions} target positions, and "
                f"{'small caps allowed' if payload.mandate.allow_small_caps else 'small caps excluded'}."
            ),
        )
        notes.insert(
            2,
            (
                f"Mandate decisions used a {mandate_config.decision_lookback_days}-day decision window and "
                f"{mandate_config.holding_period_days}-day holding target, while the ensemble loader kept up to "
                f"{history_lookback_days} calendar days available for model features."
            ),
        )

    used_ml_count = sum(1 for snapshot, _ in model_portfolio if snapshot.expected_return_source == "ENSEMBLE")
    top_model_drivers_by_symbol = {
        snapshot.symbol: list(snapshot.top_model_drivers) for snapshot, _ in model_portfolio if snapshot.top_model_drivers
    }
    model_source = "ENSEMBLE" if used_ml_count > 0 else "RULES"
    model_version = next((snapshot.model_version for snapshot, _ in model_portfolio if snapshot.expected_return_source == "ENSEMBLE"), "rules")
    prediction_horizon_days = next((snapshot.prediction_horizon_days for snapshot, _ in model_portfolio if snapshot.expected_return_source == "ENSEMBLE"), 21)
    if payload.model_variant == "LIGHTGBM_HYBRID":
        if used_ml_count > 0:
            notes.append(
                f"Ensemble runtime used for {used_ml_count} equities during backtest selection. Model version: {model_version}."
            )
        else:
            notes.append("Ensemble runtime was requested, but no valid equity predictions were produced for the backtest selection.")

    db.add(
        BacktestRun(
            id=run_id,
            strategy_name=payload.strategy_name,
            risk_mode=runtime_risk_mode,
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
    top_model_drivers_by_symbol = model_info.get("top_model_drivers_by_symbol", {})
    return BacktestResultResponse(
        model_variant=model_variant,
        model_source=model_source,  # type: ignore[arg-type]
        model_version=model_version,
        prediction_horizon_days=prediction_horizon_days,
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
    runtime_status = get_model_runtime_status()
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
    benchmark_reference_returns = aggregate_portfolio_returns(snapshot_map, benchmark_portfolios.get("Nifty 50 Proxy", {}))

    strategies = []
    for name, category, description in BENCHMARK_UNIVERSES:
        strategy_returns = aggregate_portfolio_returns(snapshot_map, benchmark_portfolios.get(name, {}))
        metrics = summarize_return_series(strategy_returns)
        expense_ratio = 0.08 if category == "AI" else 0.06 if category == "INDEX" else 0.34
        benchmark_metadata = BENCHMARK_METADATA.get(name, {})
        relative_accuracy_score_pct = compute_relative_outperformance_score(strategy_returns, benchmark_reference_returns)
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
                source_type="LOCAL_PROXY",
                source_provider="local_research",
                relative_accuracy_score_pct=relative_accuracy_score_pct,
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
        "Benchmark beat rate is the share of overlapping trading days each strategy matched or outperformed the Nifty 50 proxy return.",
    ]
    return BenchmarkSummaryResponse(
        strategies=strategies,
        projected_growth=projected_growth,
        runtime=build_runtime_descriptor(runtime_status),
        notes=notes,
    )


def build_market_dashboard(db: Session) -> MarketDashboardResponse:
    as_of_date = get_effective_trade_date(db)
    runtime_status = get_model_runtime_status()
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=126)
    if not snapshots:
        raise ValueError("No market data is available yet. Ingest bhavcopy data first.")

    benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
    reference = benchmark or max(snapshots, key=lambda snapshot: snapshot.avg_traded_value)
    closes = [price for _, price in reference.adjusted_closes]
    dma50 = sum(closes[-50:]) / max(min(len(closes), 50), 1)
    dma200 = sum(closes[-200:]) / max(min(len(closes), 200), 1)
    breadth_50_count = 0
    breadth_50_total = 0
    breadth_200_count = 0
    breadth_200_total = 0
    for snapshot in snapshots:
        series = [price for _, price in snapshot.adjusted_closes]
        if len(series) >= 50:
            breadth_50_total += 1
            breadth_50_count += int(series[-1] > (sum(series[-50:]) / 50))
        if len(series) >= 200:
            breadth_200_total += 1
            breadth_200_count += int(series[-1] > (sum(series[-200:]) / 200))
    drawdown_pct = compute_max_drawdown(closes) * 100.0
    drawdown_state = "Deep drawdown" if drawdown_pct >= 20 else "Pullback" if drawdown_pct >= 10 else "Trend intact"

    factor_weather = [
        MarketFactorWeatherItemModel(
            factor="momentum",
            leadership_score=round(sum(snapshot.factor_scores.get("momentum", 0.0) for snapshot in snapshots) / len(snapshots), 2),
            leader=max(snapshots, key=lambda snapshot: snapshot.factor_scores.get("momentum", 0.0)).symbol,
            note="Cross-sectional momentum leadership from local price history.",
            data_quality="live",
        ),
        MarketFactorWeatherItemModel(
            factor="quality",
            leadership_score=round(sum(snapshot.factor_scores.get("quality", 0.0) for snapshot in snapshots) / len(snapshots), 2),
            leader=max(snapshots, key=lambda snapshot: snapshot.factor_scores.get("quality", 0.0)).symbol,
            note="Quality proxy combines drawdown control, downside volatility, and stability.",
            data_quality="proxy",
        ),
        MarketFactorWeatherItemModel(
            factor="low-vol",
            leadership_score=round(sum(snapshot.factor_scores.get("low_vol", 0.0) for snapshot in snapshots) / len(snapshots), 2),
            leader=max(snapshots, key=lambda snapshot: snapshot.factor_scores.get("low_vol", 0.0)).symbol,
            note="Low-vol leadership from realized volatility ranking.",
            data_quality="live",
        ),
        MarketFactorWeatherItemModel(
            factor="value/size",
            leadership_score=round(sum(snapshot.factor_scores.get("size", 0.0) for snapshot in snapshots) / len(snapshots), 2),
            leader=max(snapshots, key=lambda snapshot: snapshot.factor_scores.get("size", 0.0)).symbol,
            note="Market-cap bucket proxy used until explicit value and earnings datasets are wired in.",
            data_quality="proxy",
        ),
    ]

    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots}
    gold_proxy = snapshot_map.get("GOLDBEES")
    liquid_proxy = snapshot_map.get("LIQUIDBEES")
    energy_sector = [snapshot for snapshot in snapshots if snapshot.sector == "Energy"]
    it_sector = [snapshot for snapshot in snapshots if snapshot.sector == "IT"]
    finance_sector = [snapshot for snapshot in snapshots if snapshot.sector in {"Banking", "Finance"}]
    cross_asset_tone = [
        CrossAssetToneItemModel(
            asset="Rates",
            tone="risk-off" if liquid_proxy and liquid_proxy.momentum_1m_pct > 0.8 else "neutral",
            move_pct=round(liquid_proxy.momentum_1m_pct if liquid_proxy else 0.0, 2),
            note="Liquid ETF trend used as a local rates/liquidity proxy.",
            data_quality="proxy",
        ),
        CrossAssetToneItemModel(
            asset="INR",
            tone="exporter tailwind" if (sum(snapshot.momentum_1m_pct for snapshot in it_sector) / max(len(it_sector), 1)) > 0 else "importer relief",
            move_pct=round((sum(snapshot.momentum_1m_pct for snapshot in it_sector) / max(len(it_sector), 1)) - (sum(snapshot.momentum_1m_pct for snapshot in energy_sector) / max(len(energy_sector), 1)), 2),
            note="Exporter vs importer sector spread is being used until direct INR data is added.",
            data_quality="proxy",
        ),
        CrossAssetToneItemModel(
            asset="Crude",
            tone="inflationary" if energy_sector and (sum(snapshot.momentum_1m_pct for snapshot in energy_sector) / len(energy_sector)) > 0 else "benign",
            move_pct=round(sum(snapshot.momentum_1m_pct for snapshot in energy_sector) / max(len(energy_sector), 1), 2),
            note="Energy-sector trend used as a crude sensitivity proxy.",
            data_quality="proxy",
        ),
        CrossAssetToneItemModel(
            asset="Gold",
            tone="defensive demand" if gold_proxy and gold_proxy.momentum_1m_pct > 0 else "risk-on",
            move_pct=round(gold_proxy.momentum_1m_pct if gold_proxy else 0.0, 2),
            note="Gold ETF returns are live where available.",
            data_quality="live" if gold_proxy else "proxy",
        ),
        CrossAssetToneItemModel(
            asset="Credit/Liquidity",
            tone="tightening" if finance_sector and (sum(snapshot.max_drawdown_pct for snapshot in finance_sector) / len(finance_sector)) > 20 else "stable",
            move_pct=round(-(sum(snapshot.max_drawdown_pct for snapshot in finance_sector) / max(len(finance_sector), 1)), 2),
            note="Financial-sector drawdown and liquid ETF trend are standing in for direct credit-spread feeds.",
            data_quality="proxy",
        ),
    ]

    sector_groups: dict[str, list[Snapshot]] = defaultdict(list)
    for snapshot in snapshots:
        if snapshot.instrument_type == "EQUITY":
            sector_groups[snapshot.sector].append(snapshot)
    sector_relative_strength = [
        SectorRelativeStrengthModel(
            sector=sector,
            return_1m_pct=round(sum(snapshot.momentum_1m_pct for snapshot in members) / len(members), 2),
            return_3m_pct=round(sum(snapshot.momentum_3m_pct for snapshot in members) / len(members), 2),
            return_6m_pct=round(sum(snapshot.momentum_6m_pct for snapshot in members) / len(members), 2),
            earnings_revision_trend=(
                "Positive proxy"
                if (sum(snapshot.factor_scores.get("quality", 0.0) for snapshot in members) / len(members)) > 0.2
                else "Negative proxy"
                if (sum(snapshot.factor_scores.get("quality", 0.0) for snapshot in members) / len(members)) < -0.2
                else "Neutral proxy"
            ),
            note="Earnings revision feed is not live yet; current label is a quality/stability proxy.",
        )
        for sector, members in sector_groups.items()
        if members
    ]
    sector_relative_strength.sort(key=lambda item: (item.return_3m_pct, item.return_1m_pct), reverse=True)

    breadth_50_pct = (breadth_50_count / breadth_50_total) * 100.0 if breadth_50_total else 0.0
    breadth_200_pct = (breadth_200_count / breadth_200_total) * 100.0 if breadth_200_total else 0.0
    risk_level = (
        "favorable"
        if reference.latest_price > dma200 and breadth_50_pct >= 55 and reference.annual_volatility_pct <= 18
        else "mixed"
        if reference.latest_price > dma200 or breadth_50_pct >= 50
        else "fragile"
    )
    next_action = (
        "Lean into leadership but keep an eye on cap usage."
        if risk_level == "favorable"
        else "Prefer balanced books and stagger new risk."
        if risk_level == "mixed"
        else "Stay selective, keep dry powder, and favor defensives."
    )

    return MarketDashboardResponse(
        runtime=build_runtime_descriptor(runtime_status),
        trend=MarketTrendBlockModel(
            index_symbol=reference.symbol,
            spot=round(reference.latest_price, 2),
            dma50=round(dma50, 2),
            dma200=round(dma200, 2),
            above_50_dma=reference.latest_price > dma50,
            above_200_dma=reference.latest_price > dma200,
            breadth_above_50_pct=round(breadth_50_pct, 2),
            breadth_above_200_pct=round(breadth_200_pct, 2),
            realized_volatility_pct=round(reference.annual_volatility_pct, 2),
            drawdown_pct=round(drawdown_pct, 2),
            drawdown_state=drawdown_state,
        ),
        factor_weather=factor_weather,
        cross_asset_tone=cross_asset_tone,
        sector_relative_strength=sector_relative_strength[:10],
        what_this_means_now=build_portfolio_fit_summary(
            risk_level=risk_level,
            diversification=f"breadth {breadth_50_pct:.0f}% above 50 DMA and {breadth_200_pct:.0f}% above 200 DMA",
            concentration=f"sector leaders are {_join_list([item.sector for item in sector_relative_strength[:3]])}" if sector_relative_strength else "sector leadership is broad but unconfirmed",
            next_action=next_action,
        ),
        notes=[
            f"Market dashboard uses local prices through {as_of_date.isoformat()}.",
            "Cross-asset and earnings-revision blocks are clearly labeled as proxies until dedicated feeds are wired in.",
        ],
    )


def build_benchmark_compare(db: Session, payload: BenchmarkCompareRequest) -> BenchmarkCompareResponse:
    as_of_date = get_effective_trade_date(db)
    runtime_status = get_model_runtime_status()
    runtime = build_runtime_descriptor(runtime_status)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=126)
    if not snapshots:
        raise ValueError("No benchmark data is available yet. Ingest bhavcopy data first.")
    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots}

    strategy_weights: dict[str, float]
    strategy_name = "Generated Mandate"
    strategy_match_basis = "live portfolio weights"
    if payload.allocations:
        total_weight = sum(item.weight_pct for item in payload.allocations) or 1.0
        strategy_weights = {
            item.symbol: max(item.weight_pct, 0.0) / total_weight
            for item in payload.allocations
            if item.symbol in snapshot_map
        }
    elif payload.mandate is not None:
        mandate_config = derive_mandate_config(payload.mandate)
        model_variant = payload.model_variant or runtime.variant
        selected = select_portfolio_candidates_for_mandate(
            db,
            as_of_date,
            payload.mandate,
            snapshots,
            mandate_config,
            model_variant=model_variant,
        )
        strategy_weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in selected}
        strategy_name = "Mandate Target Book"
        strategy_match_basis = f"{payload.mandate.risk_attitude.replace('_', ' ')} mandate with {payload.mandate.preferred_num_positions} positions"
    else:
        selected = select_portfolio_candidates(db, as_of_date, "MODERATE", snapshots, model_variant=runtime.variant)
        strategy_weights = {snapshot.symbol: weight / 100.0 for snapshot, weight in selected}
        strategy_name = "House Moderate Book"
        strategy_match_basis = "fallback moderate profile"

    if not strategy_weights:
        raise ValueError("No eligible securities were available for the compare view.")

    holding_count = len(strategy_weights)
    matched_benchmark = payload.benchmark_name or infer_benchmark_name_for_mandate(payload.mandate, holding_count)
    benchmark_portfolios = {
        "Nifty 50 Proxy": build_nifty50_proxy_portfolio(snapshots),
        "Nifty 500 Proxy": build_nifty500_proxy_portfolio(snapshots),
        "Momentum Factor": build_factor_portfolio(snapshots, factor_key="momentum", count=max(12, holding_count), sector_cap=0.24),
        "Quality Factor": build_factor_portfolio(snapshots, factor_key="quality", count=max(12, holding_count), sector_cap=0.24),
        "AMC Multi Factor": build_multifactor_portfolio(snapshots, count=max(15, holding_count), sector_cap=0.22),
    }
    base_benchmark_weights = benchmark_portfolios.get(matched_benchmark) or benchmark_portfolios["Nifty 500 Proxy"]
    comparison_sets = {
        strategy_name: strategy_weights,
        matched_benchmark: base_benchmark_weights,
        ("Nifty 500 Proxy" if matched_benchmark != "Nifty 500 Proxy" else "Nifty 50 Proxy"): benchmark_portfolios["Nifty 500 Proxy" if matched_benchmark != "Nifty 500 Proxy" else "Nifty 50 Proxy"],
    }
    benchmark_returns = aggregate_portfolio_returns(snapshot_map, base_benchmark_weights)

    series_by_name = {name: aggregate_portfolio_returns(snapshot_map, weights) for name, weights in comparison_sets.items()}
    base_metrics = summarize_return_series(series_by_name[strategy_name])
    strategy_turnover = estimate_turnover_pct([weight * 100.0 for weight in strategy_weights.values()], runtime.prediction_horizon_days)

    strategy_rows: list[BenchmarkCompareStatsModel] = []
    for name, weights in comparison_sets.items():
        return_series = series_by_name[name]
        metrics = summarize_return_series(return_series)
        tracking_error_pct, information_ratio = compute_tracking_error_and_ir(return_series, benchmark_returns)
        downside_capture_pct, upside_capture_pct = compute_capture_ratios(return_series, benchmark_returns)
        drawdown_duration_days, recovery_days = compute_drawdown_timing(return_series)
        holding_period_days = (
            max(21, runtime.prediction_horizon_days)
            if name == strategy_name
            else 252
            if "Nifty" in name
            else 63
        )
        turnover_pct = (
            strategy_turnover
            if name == strategy_name
            else estimate_turnover_pct([weight * 100.0 for weight in weights.values()], holding_period_days)
        )
        net_of_cost_return_pct, net_of_tax_return_pct = estimate_statutory_cost_and_tax_drag(
            metrics["annual_return_pct"],
            weights=weights,
            snapshot_map=snapshot_map,
            turnover_pct=turnover_pct,
            holding_period_days=holding_period_days,
            trade_date=as_of_date,
        )
        strategy_rows.append(
            BenchmarkCompareStatsModel(
                strategy_name=name,
                annual_return_pct=metrics["annual_return_pct"],
                volatility_pct=metrics["volatility_pct"],
                sharpe_ratio=metrics["sharpe_ratio"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                tracking_error_pct=0.0 if name == matched_benchmark else tracking_error_pct,
                information_ratio=0.0 if name == matched_benchmark else information_ratio,
                downside_capture_pct=100.0 if name == matched_benchmark else downside_capture_pct,
                upside_capture_pct=100.0 if name == matched_benchmark else upside_capture_pct,
                drawdown_duration_days=drawdown_duration_days,
                recovery_days=recovery_days,
                active_share_pct=0.0 if name == matched_benchmark else round(compute_active_share(weights, base_benchmark_weights), 2),
                net_of_cost_return_pct=net_of_cost_return_pct,
                net_of_tax_return_pct=round(net_of_tax_return_pct, 2),
                ex_ante_alpha_pct=round(metrics["annual_return_pct"] - summarize_return_series(benchmark_returns)["annual_return_pct"], 2),
                benchmark_name=matched_benchmark,
                matched_on=f"risk target and breadth around {holding_count} holdings",
            )
        )

    rolling_payload: list[BenchmarkSeriesPointModel] = []
    combined_dates = sorted({trade_date for series in series_by_name.values() for trade_date in series})
    rolling_cache = {name: rolling_window_stats(series, benchmark_returns) for name, series in series_by_name.items()}
    for idx, trade_date in enumerate(combined_dates):
        if idx % 5 != 0 and idx != len(combined_dates) - 1:
            continue
        rolling_payload.append(
            BenchmarkSeriesPointModel(
                date=trade_date,
                strategy_returns={name: round(series.get(trade_date, 0.0) * 100.0, 2) for name, series in series_by_name.items()},
                rolling_excess_return={name: values[0].get(trade_date, 0.0) for name, values in rolling_cache.items()},
                rolling_sharpe={name: values[1].get(trade_date, 0.0) for name, values in rolling_cache.items()},
            )
        )

    strategy_rows.sort(key=lambda item: (item.strategy_name != strategy_name, -item.sharpe_ratio))
    portfolio_fit_summary = build_portfolio_fit_summary(
        risk_level=f"{base_metrics['volatility_pct']:.1f}% vol vs {matched_benchmark}",
        diversification=f"active share {compute_active_share(strategy_weights, base_benchmark_weights):.1f}% against the matched benchmark",
        concentration=f"{holding_count} holdings matched against {matched_benchmark}",
        next_action=(
            "Keep the current mandate if active share remains high with positive information ratio."
            if strategy_rows[0].information_ratio > 0
            else "Tighten breadth or reduce active bets if tracking error is not paying off."
        ),
    )

    return BenchmarkCompareResponse(
        runtime=runtime,
        portfolio_fit_summary=portfolio_fit_summary,
        benchmark_match_summary=f"Compared {strategy_name} against {matched_benchmark} because it best matches the portfolio's risk target and breadth ({strategy_match_basis}).",
        strategies=strategy_rows,
        series=rolling_payload,
        notes=[
            f"Compare view uses prices through {as_of_date.isoformat()}.",
            "Net-of-cost and net-of-tax numbers use the same local equity fee schedule and capital-gains rule set as the backtest, with turnover-based realization assumptions.",
        ],
    )


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


def select_portfolio_candidates_for_mandate(
    db: Session,
    as_of_date: date,
    mandate,
    snapshots: list[Snapshot],
    mandate_config: MandateConfig,
    model_variant: ModelVariant = "RULES",
) -> list[tuple[Snapshot, float]]:
    filtered = filter_snapshots_for_mandate(snapshots, mandate_config)
    if len(filtered) < min(4, mandate_config.target_positions):
        return []

    news_signals = compute_stock_news_signals(filtered, mandate)
    for snapshot in filtered:
        signal = news_signals.get(snapshot.symbol)
        if signal is None:
            continue
        snapshot.news_risk_score = signal.news_risk_score
        snapshot.news_opportunity_score = signal.news_opportunity_score
        snapshot.news_sentiment = signal.news_sentiment
        snapshot.news_impact = signal.news_impact
        snapshot.news_explanation = signal.news_explanation

    if model_variant == "LIGHTGBM_HYBRID":
        apply_ensemble_predictions_to_snapshots(db, filtered, as_of_date, required=True)

    screened = shortlist_candidates_for_mandate(filtered, mandate, mandate_config)
    if len(screened) < min(4, mandate_config.target_positions):
        return []

    aligned_snapshots, return_matrix = align_return_matrix(screened)
    if len(aligned_snapshots) < min(4, mandate_config.target_positions) or len(return_matrix[0]) < 20:
        return []

    expected_returns = estimate_expected_returns_for_mandate(
        db,
        as_of_date,
        aligned_snapshots,
        return_matrix,
        mandate,
        mandate_config,
        model_variant=model_variant,
    )
    covariance_matrix = build_shrunk_covariance(return_matrix, shrinkage_for_mandate(mandate))
    optimized_weights = optimize_constrained_allocator_for_mandate(
        aligned_snapshots,
        expected_returns,
        covariance_matrix,
        mandate,
        mandate_config,
    )
    if not optimized_weights:
        return []
        
    all_prior = build_prior_weights_for_mandate(aligned_snapshots, mandate, mandate_config)
    
    ordered = sorted(
        zip(aligned_snapshots, optimized_weights, all_prior),
        key=lambda item: item[1],
        reverse=True,
    )
    diversified_selection = choose_diversified_mandate_constituents(ordered, mandate_config)
    if not diversified_selection:
        return []
    
    top_snapshots = [item[0] for item in diversified_selection]
    top_weights = [item[1] for item in diversified_selection]
    top_prior = [item[2] for item in diversified_selection]
    
    regime_dict = detect_market_regime(aligned_snapshots)
    regime_name = str(regime_dict.get("regime", "neutral"))
    if regime_name == "sideways":
        regime_name = "neutral"
    
    final_weights = project_weights_for_mandate(top_weights, top_snapshots, mandate_config, top_prior, regime_name)
    
    result = [(s, round(w * 100, 2)) for s, w in zip(top_snapshots, final_weights)]
    
    total_pct = sum(w for _, w in result)
    if result and abs(total_pct - 100.0) < 2.0 and abs(total_pct - 100.0) > 1e-4:
        max_idx = max(range(len(result)), key=lambda i: result[i][1])
        diff = round(100.0 - total_pct, 2)
        s, w = result[max_idx]
        result[max_idx] = (s, round(w + diff, 2))
        
    return [x for x in result if x[1] > 0]


def filter_snapshots_for_mandate(snapshots: list[Snapshot], mandate_config: MandateConfig) -> list[Snapshot]:
    filtered: list[Snapshot] = []
    for snapshot in snapshots:
        market_cap_bucket = snapshot.market_cap_bucket or "Unknown"
        if market_cap_bucket == "Small" and "Small" not in mandate_config.allowed_market_caps:
            continue
        if snapshot.annual_volatility_pct > mandate_config.max_annual_volatility_pct:
            continue
        if death_risk_proxy(snapshot) > mandate_config.max_death_risk:
            continue
        filtered.append(snapshot)
    return filtered


def shortlist_candidates_for_mandate(
    snapshots: list[Snapshot],
    mandate,
    mandate_config: MandateConfig,
) -> list[Snapshot]:
    scored = sorted(
        snapshots,
        key=lambda snapshot: candidate_score_for_mandate(snapshot, mandate, mandate_config),
        reverse=True,
    )
    return scored[:mandate_config.candidate_count]


def candidate_score_for_mandate(snapshot: Snapshot, mandate, mandate_config: MandateConfig) -> float:
    selection_bias = mandate_config.selection_bias
    momentum = snapshot.factor_scores.get("momentum", 0.0)
    quality = snapshot.factor_scores.get("quality", 0.0)
    low_vol = snapshot.factor_scores.get("low_vol", 0.0)
    sector_strength = snapshot.factor_scores.get("sector_strength", 0.0)
    liquidity = snapshot.factor_scores.get("liquidity", 0.0)
    beta_alignment = max(0.0, 1.5 - abs(snapshot.beta_proxy - mandate_config.preferred_beta))
    base_score = (
        (13.0 * momentum * selection_bias.get("momentum", 1.0))
        + (12.0 * quality * selection_bias.get("quality", 1.0))
        + (8.0 * low_vol * selection_bias.get("low_vol", 1.0))
        + (6.0 * sector_strength * selection_bias.get("sector_strength", 1.0))
        + (4.0 * liquidity * selection_bias.get("liquidity", 1.0))
        + (6.0 * beta_alignment)
    )
    if mandate.risk_attitude == "capital_preservation":
        base_score += 5.0 * low_vol + 4.0 * quality
    elif mandate.risk_attitude == "growth":
        base_score += 6.0 * momentum + 3.5 * snapshot.factor_scores.get("beta", 0.0)

    news_adjustment = (
        (snapshot.news_opportunity_score * 9.0 * mandate_config.news_boost_multiplier * selection_bias.get("news", 1.0))
        - (snapshot.news_risk_score * 11.0 * mandate_config.news_penalty_multiplier * selection_bias.get("news", 1.0))
    )
    ensemble_bonus = 0.0
    if snapshot.ml_pred_21d_return is not None:
        ensemble_bonus += 18.0 * float(snapshot.ml_pred_21d_return)
    if snapshot.ml_pred_annual_return is not None:
        ensemble_bonus += 10.0 * float(snapshot.ml_pred_annual_return)
    return base_score + news_adjustment + ensemble_bonus + min(snapshot.avg_traded_value / 50_000_000.0, 6.0)


def apply_ensemble_predictions_to_snapshots(
    db: Session,
    snapshots: list[Snapshot],
    as_of_date: date,
    *,
    required: bool,
) -> dict[str, object]:
    for snapshot in snapshots:
        snapshot.expected_return_source = "RULES"
        snapshot.model_version = "rules"
        snapshot.ml_pred_21d_return = None
        snapshot.ml_pred_annual_return = None
        snapshot.top_model_drivers = []
        snapshot.prediction_horizon_days = 21

    if not snapshots:
        if required:
            raise ValueError("Ensemble runtime was requested, but there were no snapshots to score.")
        return {"available": False, "reason": "no_snapshots"}

    try:
        predictions_by_symbol, model_info = predict_ensemble_for_snapshots(db, snapshots, as_of_date)
    except Exception as exc:
        if required:
            raise ValueError(f"Ensemble runtime failed during inference: {exc}") from exc
        return {"available": False, "reason": "ensemble_inference_failed"}

    if required and not predictions_by_symbol:
        detail_parts: list[str] = []
        reason = model_info.get("reason")
        if reason:
            detail_parts.append(f"reason={reason}")
        invalid_rows = model_info.get("invalid_rows")
        if isinstance(invalid_rows, list) and invalid_rows:
            detail_parts.append(f"invalid_rows={len(invalid_rows)}")
        refreshed = model_info.get("history_refreshed_symbols")
        if isinstance(refreshed, list) and refreshed:
            detail_parts.append(f"history_refreshed={len(refreshed)}")
        insufficient_history = model_info.get("insufficient_history_symbols")
        if isinstance(insufficient_history, list) and insufficient_history:
            detail_parts.append(f"still_short_history={len(insufficient_history)}")
        detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
        raise ValueError(f"Ensemble runtime was requested, but it returned no usable predictions{detail}.")

    model_version = str(model_info.get("model_version", "ensemble"))
    prediction_horizon_days = int(model_info.get("prediction_horizon_days", 21))
    for snapshot in snapshots:
        pred = predictions_by_symbol.get(snapshot.symbol)
        if snapshot.instrument_type != "EQUITY" or pred is None:
            continue
        snapshot.ml_pred_21d_return = float(pred.pred_21d_return)
        snapshot.ml_pred_annual_return = float(pred.pred_annual_return)
        snapshot.top_model_drivers = list(pred.top_drivers)
        snapshot.expected_return_source = "ENSEMBLE"
        snapshot.model_version = model_version
        snapshot.prediction_horizon_days = prediction_horizon_days

    if required and not any(snapshot.expected_return_source == "ENSEMBLE" for snapshot in snapshots):
        raise ValueError("Ensemble runtime was requested, but no equity snapshots received usable predictions.")

    return model_info


def estimate_expected_returns_for_mandate(
    db: Session,
    as_of_date: date,
    snapshots: list[Snapshot],
    return_matrix: list[list[float]],
    mandate,
    mandate_config: MandateConfig,
    model_variant: ModelVariant = "RULES",
) -> list[float]:
    regime = detect_market_regime(snapshots)
    holding_scale = mandate_holding_period_scale(mandate_config)
    rule_expected_returns: list[float] = []
    for index, snapshot in enumerate(snapshots):
        series = return_matrix[index]
        daily_mean = sum(series) / max(len(series), 1)
        annual_mean = daily_mean * 252
        momentum = snapshot.factor_scores.get("momentum", 0.0)
        quality = snapshot.factor_scores.get("quality", 0.0)
        low_vol = snapshot.factor_scores.get("low_vol", 0.0)
        sector_strength = snapshot.factor_scores.get("sector_strength", 0.0)
        beta_penalty = abs(snapshot.beta_proxy - mandate_config.preferred_beta) * 0.014
        news_adjustment = (
            (snapshot.news_opportunity_score * 0.05 * mandate_config.news_boost_multiplier)
            - (snapshot.news_risk_score * 0.06 * mandate_config.news_penalty_multiplier)
        )
        expected = (
            regime["base_return"]
            + (0.34 * annual_mean * holding_scale)
            + (0.026 * momentum)
            + (0.020 * quality)
            + (0.014 * low_vol)
            + (0.012 * sector_strength)
            + news_adjustment
            - beta_penalty
        )
        if mandate.risk_attitude == "capital_preservation":
            expected -= max(0.0, snapshot.annual_volatility_pct - mandate_config.max_annual_volatility_pct) * 0.002
        elif mandate.risk_attitude == "growth":
            expected += regime["risk_on_bonus"] + (0.008 * snapshot.factor_scores.get("beta", 0.0))
        rule_expected_returns.append(max(-0.15, min(0.35, expected)))

    if model_variant != "LIGHTGBM_HYBRID":
        for snapshot in snapshots:
            snapshot.expected_return_source = "RULES"
            snapshot.model_version = "rules"
            snapshot.ml_pred_21d_return = None
            snapshot.ml_pred_annual_return = None
            snapshot.top_model_drivers = []
            snapshot.prediction_horizon_days = 21
        return rule_expected_returns

    predictions_by_symbol = {
        snapshot.symbol: snapshot
        for snapshot in snapshots
        if snapshot.expected_return_source == "ENSEMBLE" and snapshot.ml_pred_annual_return is not None
    }
    if not predictions_by_symbol:
        apply_ensemble_predictions_to_snapshots(db, snapshots, as_of_date, required=True)
        predictions_by_symbol = {
            snapshot.symbol: snapshot
            for snapshot in snapshots
            if snapshot.expected_return_source == "ENSEMBLE" and snapshot.ml_pred_annual_return is not None
        }

    expected_returns = rule_expected_returns[:]
    for index, snapshot in enumerate(snapshots):
        pred_snapshot = predictions_by_symbol.get(snapshot.symbol)
        if snapshot.instrument_type != "EQUITY" or pred_snapshot is None or pred_snapshot.ml_pred_annual_return is None:
            continue
        ml_expected = float(pred_snapshot.ml_pred_annual_return)
        news_tilt = (
            snapshot.news_opportunity_score * 0.01 * mandate_config.news_boost_multiplier
            - snapshot.news_risk_score * 0.015 * mandate_config.news_penalty_multiplier
        )
        expected_returns[index] = max(-0.15, min(0.35, (ml_expected * holding_scale) + news_tilt))

    return expected_returns


def optimize_constrained_allocator_for_mandate(
    snapshots: list[Snapshot],
    expected_returns: list[float],
    covariance_matrix: list[list[float]],
    mandate,
    mandate_config: MandateConfig,
) -> list[float]:
    if not snapshots:
        return []

    prior = build_prior_weights_for_mandate(snapshots, mandate, mandate_config)
    weights = prior[:]
    for iteration in range(220):
        sigma_w = matrix_vector_product(covariance_matrix, weights)
        gradient: list[float] = []
        for index, snapshot in enumerate(snapshots):
            news_alpha = (
                snapshot.news_opportunity_score * 0.02 * mandate_config.news_boost_multiplier
                - snapshot.news_risk_score * 0.025 * mandate_config.news_penalty_multiplier
            )
            gradient.append(
                expected_returns[index]
                + news_alpha
                - (mandate_config.risk_aversion * sigma_w[index])
            )
        step_size = 0.18 / (1 + (iteration / 35))
        proposal = [(weight + (step_size * grad)) for weight, grad in zip(weights, gradient)]
        weights = project_weights_for_mandate(proposal, snapshots, mandate_config, prior)

    cleaned = [weight if weight >= 0.005 else 0.0 for weight in weights]
    return renormalize(cleaned)


def choose_diversified_mandate_constituents(
    ordered: list[tuple[Snapshot, float, float]],
    mandate_config: MandateConfig,
) -> list[tuple[Snapshot, float, float]]:
    target_count = min(mandate_config.target_positions, len(ordered))
    if target_count <= 0:
        return []

    selected: list[tuple[Snapshot, float, float]] = []
    selected_symbols: set[str] = set()
    sector_counts: dict[str, int] = defaultdict(int)
    sector_universe = {snapshot.sector for snapshot, _, _ in ordered}
    sector_target = min(mandate_config.min_sector_count, len(sector_universe), target_count)

    for item in ordered:
        snapshot, _, _ = item
        if len(selected) >= sector_target:
            break
        if snapshot.symbol in selected_symbols or sector_counts[snapshot.sector] > 0:
            continue
        selected.append(item)
        selected_symbols.add(snapshot.symbol)
        sector_counts[snapshot.sector] += 1

    for item in ordered:
        snapshot, _, _ = item
        if len(selected) >= target_count:
            break
        if snapshot.symbol in selected_symbols:
            continue
        if sector_counts[snapshot.sector] >= mandate_config.max_positions_per_sector:
            continue
        selected.append(item)
        selected_symbols.add(snapshot.symbol)
        sector_counts[snapshot.sector] += 1

    for item in ordered:
        snapshot, _, _ = item
        if len(selected) >= target_count:
            break
        if snapshot.symbol in selected_symbols:
            continue
        selected.append(item)
        selected_symbols.add(snapshot.symbol)

    return selected


def build_prior_weights_for_mandate(
    snapshots: list[Snapshot],
    mandate,
    mandate_config: MandateConfig,
) -> list[float]:
    raw: list[float] = []
    selection_bias = mandate_config.selection_bias
    for snapshot in snapshots:
        base = (
            1.0
            + (0.35 * snapshot.factor_scores.get("momentum", 0.0) * selection_bias.get("momentum", 1.0))
            + (0.30 * snapshot.factor_scores.get("quality", 0.0) * selection_bias.get("quality", 1.0))
        )
        if mandate.risk_attitude == "capital_preservation":
            base += (0.35 * snapshot.factor_scores.get("low_vol", 0.0) * selection_bias.get("low_vol", 1.0))
        elif mandate.risk_attitude == "growth":
            base += (0.20 * snapshot.factor_scores.get("beta", 0.0))
        base += snapshot.news_opportunity_score * 0.4 * selection_bias.get("news", 1.0)
        base -= snapshot.news_risk_score * 0.45 * selection_bias.get("news", 1.0)
        if "BEES" in snapshot.symbol or snapshot.sector == "Index":
            base *= 0.1
        raw.append(max(0.05, base))
    total = sum(raw)
    return [value / max(total, 1e-9) for value in raw]


def project_weights_for_mandate(
    weights: list[float],
    snapshots: list[Snapshot],
    mandate_config: MandateConfig,
    prior: list[float],
    regime_name: str = "neutral",
) -> list[float]:
    w = [max(0.0, weight) for weight in weights]
    if sum(w) == 0:
        w = prior[:]

    for i in range(len(w)):
        if w[i] < 0.02:
            w[i] = 0.0

    w = renormalize([min(mandate_config.max_position_weight, weight) for weight in w])

    for _ in range(12):
        w = renormalize(w)
        w = [0.82 * weight + 0.18 * base for weight, base in zip(w, prior)]
        w = renormalize([min(mandate_config.max_position_weight, max(0.0, weight)) for weight in w])

        excess_pool = 0.0
        for index in range(len(w)):
            capped = min(mandate_config.max_position_weight, w[index])
            excess_pool += max(0.0, w[index] - capped)
            w[index] = capped

        sector_totals = compute_sector_totals(w, snapshots)
        for sector, total in sector_totals.items():
            if total <= mandate_config.sector_cap_weight:
                continue
            scale = mandate_config.sector_cap_weight / max(total, 1e-9)
            for index, snapshot in enumerate(snapshots):
                if snapshot.sector != sector:
                    continue
                reduced = w[index] * (1 - scale)
                w[index] *= scale
                excess_pool += reduced

        etf_cap = 0.15
        if regime_name == "bear":
            etf_cap = 0.20
        elif regime_name == "bull":
            etf_cap = 0.10

        etf_total = sum(w[j] for j, s in enumerate(snapshots) if "BEES" in s.symbol or s.sector == "Index")
        if etf_total > etf_cap + 1e-6:
            ratio = etf_cap / max(etf_total, 1e-9)
            for index, snapshot in enumerate(snapshots):
                if "BEES" in snapshot.symbol or snapshot.sector == "Index":
                    reduced = w[index] * (1 - ratio)
                    w[index] *= ratio
                    excess_pool += reduced

        if excess_pool > 1e-9:
            w = redistribute_weight_for_mandate(w, snapshots, mandate_config, prior, excess_pool)

    return renormalize([min(mandate_config.max_position_weight, max(0.0, weight)) for weight in w])

def redistribute_weight_for_mandate(
    weights: list[float],
    snapshots: list[Snapshot],
    mandate_config: MandateConfig,
    prior: list[float],
    excess_pool: float,
) -> list[float]:
    sector_totals = compute_sector_totals(weights, snapshots)
    headroom: list[float] = []
    for index, snapshot in enumerate(snapshots):
        asset_headroom = max(0.0, mandate_config.max_position_weight - weights[index])
        sector_headroom = max(0.0, mandate_config.sector_cap_weight - sector_totals[snapshot.sector])
        score = min(asset_headroom, sector_headroom) * (1.0 + max(prior[index], 0.001))
        headroom.append(score)

    total_headroom = sum(headroom)
    if total_headroom <= 1e-9:
        return weights

    redistributed = weights[:]
    for index, score in enumerate(headroom):
        redistributed[index] += excess_pool * (score / total_headroom)
    return redistributed


def build_rationale_for_mandate(snapshot: Snapshot, mandate, mandate_config: MandateConfig) -> str:
    risk_text = (
        f"news risk {snapshot.news_risk_score:.2f}, opportunity {snapshot.news_opportunity_score:.2f}"
    )
    ensemble_text = ""
    if snapshot.ml_pred_21d_return is not None:
        ensemble_text = (
            f", ensemble 21d {snapshot.ml_pred_21d_return * 100:+.1f}%"
            + (
                f", annualized {snapshot.ml_pred_annual_return * 100:+.1f}%"
                if snapshot.ml_pred_annual_return is not None
                else ""
            )
        )
    return (
        f"{snapshot.sector} allocation for a {mandate.risk_attitude.replace('_', ' ')} mandate with a {mandate_config.holding_period_days}-day target hold; "
        f"momentum {snapshot.factor_scores.get('momentum', 0):+.2f}, quality {snapshot.factor_scores.get('quality', 0):+.2f}, "
        f"beta {snapshot.beta_proxy:.2f}{ensemble_text}, {risk_text}. {snapshot.news_explanation}"
    )


def death_risk_proxy(snapshot: Snapshot) -> float:
    score = (
        0.35 * min(snapshot.max_drawdown_pct / 45.0, 1.0)
        + 0.30 * min(snapshot.annual_volatility_pct / 40.0, 1.0)
        + 0.20 * min(max(snapshot.beta_proxy - 0.8, 0.0) / 1.2, 1.0)
        + 0.15 * (1.0 if snapshot.market_cap_bucket == "Small" else 0.35 if snapshot.market_cap_bucket == "Mid" else 0.0)
    )
    return round(min(1.0, score), 4)


def shrinkage_for_mandate(mandate) -> float:
    if mandate.risk_attitude == "capital_preservation":
        return 0.52
    if mandate.risk_attitude == "growth":
        return 0.28
    return 0.40


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


def rebalance_positions(position_state, bar_matrix, weights, trade_date, portfolio_value, costs, taxes, tax_buckets, risk_mode: str, turnover_state) -> int:
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
            turnover_state["gross_executed_notional"] += proceeds
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
            turnover_state["gross_executed_notional"] += trade_value
            trades += 1
    return trades


def build_backtest_metrics(equity_curve, portfolio_returns, costs, taxes, total_trades, gross_executed_notional) -> BacktestMetricModel:
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
    turnover_pct = (gross_executed_notional / max(initial_value, 1)) * 100
    return BacktestMetricModel(
        cagr_pct=round(cagr_pct, 2),
        total_return_pct=round(total_return_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        sortino_ratio=round(sortino_ratio, 2),
        calmar_ratio=round(calmar_ratio, 2),
        turnover_pct=round(turnover_pct, 2),
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
        predictions_by_symbol, model_info = predict_ensemble_for_snapshots(db, snapshots, as_of_date)
    except Exception:
        logger.exception("Expected return inference failed; continuing with rules-only expected returns.")
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
        snapshot.expected_return_source = "ENSEMBLE"
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


def compute_relative_outperformance_score(
    strategy_returns: dict[date, float],
    benchmark_returns: dict[date, float],
) -> float:
    overlap_dates = [trade_date for trade_date in strategy_returns if trade_date in benchmark_returns]
    if not overlap_dates:
        return 0.0

    wins = 0.0
    for trade_date in overlap_dates:
        strategy_value = strategy_returns[trade_date]
        benchmark_value = benchmark_returns[trade_date]
        if strategy_value > benchmark_value + 1e-9:
            wins += 1.0
        elif abs(strategy_value - benchmark_value) <= 1e-9:
            wins += 0.5

    return round((wins / len(overlap_dates)) * 100.0, 1)


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
    import numpy as np
    import pandas as pd

    return_maps = {
        snapshot.symbol: {trade_date: value for trade_date, value in snapshot.returns}
        for snapshot in snapshots
        if len(snapshot.returns) >= 10
    }
    if len(return_maps) < 2:
        return 0.0

    frame = pd.DataFrame(return_maps, dtype=float)
    if frame.shape[1] < 2:
        return 0.0

    corr_matrix = frame.corr(min_periods=10).to_numpy(dtype=float)
    if corr_matrix.shape[0] < 2:
        return 0.0

    upper_indices = np.triu_indices_from(corr_matrix, k=1)
    pair_values = corr_matrix[upper_indices]
    pair_values = pair_values[~np.isnan(pair_values)]
    if pair_values.size == 0:
        return 0.0
    return float(np.clip(pair_values.mean(), -1.0, 1.0))


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


def _sma(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    if len(values) < window:
        return sum(values) / len(values)
    return sum(values[-window:]) / window


def detect_market_regime(snapshots: list[Snapshot]) -> dict[str, float | str]:
    benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
    reference = benchmark or max(snapshots, key=lambda snapshot: snapshot.avg_traded_value, default=None)
    if reference is None:
        return {
            "regime": "sideways",
            "confidence": 0.0,
            "breadth_50": 0.5,
            "breadth_200": 0.5,
            "base_return": 0.10,
            "risk_on_bonus": 0.0,
        }

    closes = [price for _, price in reference.adjusted_closes]
    if not closes:
        return {
            "regime": "sideways",
            "confidence": 0.0,
            "breadth_50": 0.5,
            "breadth_200": 0.5,
            "base_return": 0.10,
            "risk_on_bonus": 0.0,
        }

    latest = closes[-1]
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)

    stocks_with_50 = 0
    stocks_with_200 = 0
    above_50 = 0
    above_200 = 0
    for snapshot in snapshots:
        series = [price for _, price in snapshot.adjusted_closes]
        if len(series) >= 50:
            stocks_with_50 += 1
            above_50 += int(series[-1] > _sma(series, 50))
        if len(series) >= 200:
            stocks_with_200 += 1
            above_200 += int(series[-1] > _sma(series, 200))

    breadth_50 = above_50 / stocks_with_50 if stocks_with_50 else 0.5
    breadth_200 = above_200 / stocks_with_200 if stocks_with_200 else 0.5
    bull_signals = sum([latest > sma200, sma50 > sma200, breadth_50 > 0.55, breadth_200 > 0.50])
    bear_signals = sum([latest < sma200, sma50 < sma200, breadth_50 < 0.45, breadth_200 < 0.45])

    if bull_signals >= 3:
        regime = "bull"
        confidence = bull_signals / 4.0
        base_return = 0.12 if confidence >= 0.75 else 0.11
        risk_on_bonus = 0.015 if confidence >= 0.75 else 0.01
    elif bear_signals >= 3:
        regime = "bear"
        confidence = bear_signals / 4.0
        base_return = 0.08 if confidence >= 0.75 else 0.09
        risk_on_bonus = -0.01 if confidence >= 0.75 else -0.005
    else:
        regime = "sideways"
        confidence = max(0.5, max(bull_signals, bear_signals) / 4.0)
        base_return = 0.10
        risk_on_bonus = 0.0

    return {
        "regime": regime,
        "confidence": round(confidence, 2),
        "breadth_50": round(breadth_50, 2),
        "breadth_200": round(breadth_200, 2),
        "base_return": base_return,
        "risk_on_bonus": risk_on_bonus,
    }


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
        # Cess is computed only from the fresh base-tax subtotal for this bucket.
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
            # Do not apply cess on any value that already includes cess.
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
