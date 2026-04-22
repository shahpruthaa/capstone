from __future__ import annotations

from dataclasses import dataclass

from app.ml.lightgbm_alpha.technical_indicators import atr_normalized
from app.services.db_quant_engine import Snapshot


@dataclass(frozen=True)
class PriceLevels:
    entry: float
    stop: float
    target: float
    atr_14d: float
    risk_pct: float
    reward_pct: float
    rr_ratio: float


def calculate_price_levels(snapshot: Snapshot, expected_return: float) -> PriceLevels:
    closes = [price for _, price in snapshot.adjusted_closes]
    highs = [price for _, price in snapshot.adjusted_highs]
    lows = [price for _, price in snapshot.adjusted_lows]
    entry = float(snapshot.latest_price)

    atr_ratio = atr_normalized(highs, lows, closes) or 0.02
    atr_value = max(entry * atr_ratio, entry * 0.01)
    stop = max(entry - (2.0 * atr_value), entry * 0.80)
    risk_per_unit = max(entry - stop, entry * 0.005)

    expected_move = max(0.0, min(0.30, float(expected_return)))
    model_target = entry * (1.0 + expected_move)
    rr_target = entry + (2.0 * risk_per_unit)
    target = max(model_target, rr_target) if expected_move > 0 else model_target

    risk_pct = (risk_per_unit / entry) * 100.0 if entry else 0.0
    reward_pct = ((target - entry) / entry) * 100.0 if entry else 0.0
    rr_ratio = (target - entry) / risk_per_unit if risk_per_unit else 0.0

    return PriceLevels(
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        atr_14d=round(atr_value, 2),
        risk_pct=round(risk_pct, 2),
        reward_pct=round(reward_pct, 2),
        rr_ratio=round(rr_ratio, 2),
    )
