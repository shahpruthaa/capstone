from __future__ import annotations

from dataclasses import dataclass

from app.schemas.portfolio import UserMandate

HORIZON_SETTINGS = {
    "2-4": {"lookback_days": 84, "holding_period_days": 21},
    "4-8": {"lookback_days": 168, "holding_period_days": 42},
    "8-24": {"lookback_days": 336, "holding_period_days": 84},
}

ATTITUDE_SETTINGS = {
    "capital_preservation": {
        "risk_aversion": 15.0,
        "candidate_multiple": 2.4,
        "max_annual_volatility_pct": 18.0,
        "max_death_risk": 0.35,
        "preferred_beta": 0.8,
        "news_penalty_multiplier": 1.25,
        "news_boost_multiplier": 0.55,
    },
    "balanced": {
        "risk_aversion": 8.5,
        "candidate_multiple": 2.8,
        "max_annual_volatility_pct": 28.0,
        "max_death_risk": 0.55,
        "preferred_beta": 1.0,
        "news_penalty_multiplier": 1.0,
        "news_boost_multiplier": 0.8,
    },
    "growth": {
        "risk_aversion": 4.8,
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
    candidate_count: int
    target_positions: int
    max_annual_volatility_pct: float
    max_death_risk: float
    preferred_beta: float
    allowed_market_caps: set[str]
    news_penalty_multiplier: float
    news_boost_multiplier: float

def derive_mandate_config(mandate: UserMandate) -> MandateConfig:
    horizon = HORIZON_SETTINGS[mandate.investment_horizon_weeks]
    attitude = ATTITUDE_SETTINGS[mandate.risk_attitude]
    target_positions = mandate.preferred_num_positions
    candidate_count = max(15, target_positions * 2, int(round(target_positions * attitude["candidate_multiple"])))
    allowed_market_caps = {"Large", "Mid", "Unknown", ""}
    if mandate.allow_small_caps:
        allowed_market_caps.add("Small")
    return MandateConfig(
        lookback_days=horizon["lookback_days"],
        holding_period_days=horizon["holding_period_days"],
        risk_aversion=attitude["risk_aversion"],
        candidate_count=candidate_count,
        target_positions=target_positions,
        max_annual_volatility_pct=attitude["max_annual_volatility_pct"],
        max_death_risk=attitude["max_death_risk"],
        preferred_beta=attitude["preferred_beta"],
        allowed_market_caps=allowed_market_caps,
        news_penalty_multiplier=attitude["news_penalty_multiplier"],
        news_boost_multiplier=attitude["news_boost_multiplier"],
    )


def build_default_mandate() -> UserMandate:
    return UserMandate(
        investment_horizon_weeks="4-8",
        preferred_num_positions=10,
        allow_small_caps=False,
        risk_attitude="balanced",
    )
