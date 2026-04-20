from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSize:
    units: int
    allocation_value: float
    allocation_pct: float
    max_loss_amount: float
    max_loss_pct: float


def calculate_position_size(
    portfolio_value: float,
    risk_per_trade_pct: float,
    entry: float,
    stop: float,
) -> PositionSize:
    if portfolio_value <= 0 or entry <= 0:
        return PositionSize(units=0, allocation_value=0.0, allocation_pct=0.0, max_loss_amount=0.0, max_loss_pct=0.0)

    loss_per_unit = max(entry - stop, entry * 0.005)
    max_loss_amount = portfolio_value * (risk_per_trade_pct / 100.0)
    max_affordable_units = int(portfolio_value // entry)
    units = min(int(max_loss_amount // loss_per_unit) if loss_per_unit > 0 else 0, max_affordable_units)
    if units <= 0 and max_affordable_units > 0:
        units = 1

    allocation_value = units * entry
    allocation_pct = (allocation_value / portfolio_value) * 100.0 if portfolio_value else 0.0

    return PositionSize(
        units=units,
        allocation_value=round(allocation_value, 2),
        allocation_pct=round(allocation_pct, 2),
        max_loss_amount=round(max_loss_amount, 2),
        max_loss_pct=round(risk_per_trade_pct, 2),
    )
