from __future__ import annotations

from dataclasses import dataclass

from app.schemas.portfolio import UserMandate


NSE_SECTOR_CODES = [
    "Auto",
    "Banking",
    "Cement",
    "Chemicals",
    "Consumer Durables",
    "Energy",
    "Finance",
    "FMCG",
    "Gold",
    "Index",
    "Infra",
    "Insurance",
    "IT",
    "Liquid",
    "Logistics",
    "Metals",
    "Pharma",
    "Real Estate",
    "Silver",
    "Tech/Internet",
    "Telecom",
    "Tourism",
]

SECTOR_ALIASES = {
    "automobile": "Auto",
    "automobiles": "Auto",
    "autos": "Auto",
    "banks": "Banking",
    "bank": "Banking",
    "financial": "Finance",
    "financials": "Finance",
    "nbfc": "Finance",
    "consumer staples": "FMCG",
    "oil": "Energy",
    "power": "Energy",
    "utilities": "Energy",
    "healthcare": "Pharma",
    "health care": "Pharma",
    "realestate": "Real Estate",
    "real-estate": "Real Estate",
    "property": "Real Estate",
    "technology": "IT",
    "tech": "IT",
    "internet": "Tech/Internet",
    "ecommerce": "Tech/Internet",
    "e-commerce": "Tech/Internet",
    "capital goods": "Infra",
    "infrastructure": "Infra",
    "telecommunications": "Telecom",
}

HORIZON_SETTINGS = {
    "2-4": {"lookback_days": 84, "holding_period_days": 21},
    "4-8": {"lookback_days": 168, "holding_period_days": 42},
    "8-24": {"lookback_days": 336, "holding_period_days": 84},
}

ATTITUDE_SETTINGS = {
    "capital_preservation": {
        "risk_aversion": 15.0,
        "sector_cap": 0.26,
        "candidate_multiple": 2.4,
        "max_annual_volatility_pct": 18.0,
        "max_death_risk": 0.35,
        "preferred_beta": 0.8,
        "news_penalty_multiplier": 1.25,
        "news_boost_multiplier": 0.55,
    },
    "balanced": {
        "risk_aversion": 8.5,
        "sector_cap": 0.30,
        "candidate_multiple": 2.8,
        "max_annual_volatility_pct": 28.0,
        "max_death_risk": 0.55,
        "preferred_beta": 1.0,
        "news_penalty_multiplier": 1.0,
        "news_boost_multiplier": 0.8,
    },
    "growth": {
        "risk_aversion": 4.8,
        "sector_cap": 0.34,
        "candidate_multiple": 3.2,
        "max_annual_volatility_pct": 42.0,
        "max_death_risk": 0.78,
        "preferred_beta": 1.2,
        "news_penalty_multiplier": 0.8,
        "news_boost_multiplier": 1.05,
    },
}


@dataclass(frozen=True)
class MandateConfig:
    lookback_days: int
    holding_period_days: int
    risk_aversion: float
    sector_cap: float
    candidate_count: int
    target_positions: int
    max_weight: float
    max_annual_volatility_pct: float
    max_death_risk: float
    preferred_beta: float
    allowed_market_caps: set[str]
    included_sectors: set[str]
    excluded_sectors: set[str]
    news_penalty_multiplier: float
    news_boost_multiplier: float


def normalize_sector_code(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return ""
    compact = normalized.replace("&", "and").replace("/", "").replace("-", "").replace(" ", "")
    alias = SECTOR_ALIASES.get(normalized) or SECTOR_ALIASES.get(compact)
    if alias:
        return alias
    for sector in NSE_SECTOR_CODES:
        sector_normalized = sector.lower()
        sector_compact = sector_normalized.replace("/", "").replace("-", "").replace(" ", "")
        if sector_normalized == normalized or sector_compact == compact:
            return sector
        if normalized in sector_normalized or sector_normalized in normalized:
            return sector
    return value.strip()


def derive_mandate_config(mandate: UserMandate) -> MandateConfig:
    if mandate.max_position_size_pct * mandate.preferred_num_positions < 100:
        raise ValueError(
            "Mandate is infeasible: `max_position_size_pct * preferred_num_positions` must be at least 100."
        )

    horizon = HORIZON_SETTINGS[mandate.investment_horizon_weeks]
    attitude = ATTITUDE_SETTINGS[mandate.risk_attitude]
    max_weight = mandate.max_position_size_pct / 100.0
    sector_cap = max(attitude["sector_cap"], min(0.5, max_weight * 2.0))
    drawdown_adjusted_vol = max(10.0, min(attitude["max_annual_volatility_pct"], mandate.max_portfolio_drawdown_pct * 1.8))
    drawdown_adjusted_death_risk = max(0.18, min(attitude["max_death_risk"], mandate.max_portfolio_drawdown_pct / 32.0))
    target_positions = mandate.preferred_num_positions
    candidate_count = max(target_positions + 4, int(round(target_positions * attitude["candidate_multiple"])))
    allowed_market_caps = {"Large", "Mid", "Unknown", ""}
    if mandate.allow_small_caps:
        allowed_market_caps.add("Small")

    included_sectors = {normalize_sector_code(value) for value in mandate.sector_inclusions if normalize_sector_code(value)}
    excluded_sectors = {normalize_sector_code(value) for value in mandate.sector_exclusions if normalize_sector_code(value)}

    overlap = included_sectors.intersection(excluded_sectors)
    if overlap:
        excluded_sectors = {sector for sector in excluded_sectors if sector not in overlap}

    return MandateConfig(
        lookback_days=horizon["lookback_days"],
        holding_period_days=horizon["holding_period_days"],
        risk_aversion=attitude["risk_aversion"],
        sector_cap=sector_cap,
        candidate_count=candidate_count,
        target_positions=target_positions,
        max_weight=max_weight,
        max_annual_volatility_pct=drawdown_adjusted_vol,
        max_death_risk=drawdown_adjusted_death_risk,
        preferred_beta=attitude["preferred_beta"],
        allowed_market_caps=allowed_market_caps,
        included_sectors=included_sectors,
        excluded_sectors=excluded_sectors,
        news_penalty_multiplier=attitude["news_penalty_multiplier"],
        news_boost_multiplier=attitude["news_boost_multiplier"],
    )


def build_default_mandate() -> UserMandate:
    return UserMandate(
        investment_horizon_weeks="4-8",
        max_portfolio_drawdown_pct=12.0,
        max_position_size_pct=12.5,
        preferred_num_positions=10,
        sector_inclusions=[],
        sector_exclusions=[],
        allow_small_caps=False,
        risk_attitude="balanced",
    )
