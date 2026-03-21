from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.corporate_action import CorporateAction
from app.models.instrument import Instrument


@dataclass(frozen=True)
class CorporateActionEvent:
    symbol: str
    ex_date: date
    action_type: str
    ratio_numerator: float | None
    ratio_denominator: float | None
    cash_amount: float | None


def load_corporate_actions(
    db: Session,
    *,
    symbols: list[str] | None = None,
    end_date: date | None = None,
) -> dict[str, list[CorporateActionEvent]]:
    stmt = (
        select(
            Instrument.symbol,
            CorporateAction.ex_date,
            CorporateAction.action_type,
            CorporateAction.ratio_numerator,
            CorporateAction.ratio_denominator,
            CorporateAction.cash_amount,
        )
        .join(CorporateAction, CorporateAction.instrument_id == Instrument.id)
        .order_by(Instrument.symbol, CorporateAction.ex_date)
    )
    if symbols:
        stmt = stmt.where(Instrument.symbol.in_(symbols))
    if end_date is not None:
        stmt = stmt.where(CorporateAction.ex_date <= end_date)

    grouped: dict[str, list[CorporateActionEvent]] = defaultdict(list)
    for row in db.execute(stmt).all():
        grouped[row.symbol].append(
            CorporateActionEvent(
                symbol=row.symbol,
                ex_date=row.ex_date,
                action_type=row.action_type.upper(),
                ratio_numerator=float(row.ratio_numerator) if row.ratio_numerator is not None else None,
                ratio_denominator=float(row.ratio_denominator) if row.ratio_denominator is not None else None,
                cash_amount=float(row.cash_amount) if row.cash_amount is not None else None,
            )
        )
    return grouped


def adjust_close_series(
    closes: list[tuple[date, float]],
    actions: list[CorporateActionEvent],
) -> tuple[list[tuple[date, float]], dict[date, float]]:
    if not closes:
        return [], {}

    cumulative_factor_by_date = build_cumulative_factor_lookup(closes, actions)
    dividend_actions = [action for action in actions if action.action_type == "DIVIDEND"]

    adjusted_closes = [(trade_date, close * cumulative_factor_by_date.get(trade_date, 1.0)) for trade_date, close in closes]
    dividend_by_date = {
        action.ex_date: (action.cash_amount or 0.0) * cumulative_factor_by_date.get(action.ex_date, 1.0)
        for action in dividend_actions
    }
    return adjusted_closes, dividend_by_date


def build_cumulative_factor_lookup(
    closes: list[tuple[date, float]],
    actions: list[CorporateActionEvent],
) -> dict[date, float]:
    if not closes:
        return {}

    split_bonus_actions = [action for action in actions if action.action_type in {"SPLIT", "BONUS"}]

    cumulative_factor_by_date: dict[date, float] = {}
    running_factor = 1.0
    split_bonus_by_date = {action.ex_date: action for action in split_bonus_actions}
    for trade_date, _ in reversed(closes):
        action = split_bonus_by_date.get(trade_date)
        if action and action.ratio_numerator and action.ratio_denominator and action.ratio_numerator > 0:
            running_factor *= action.ratio_denominator / action.ratio_numerator
        cumulative_factor_by_date[trade_date] = running_factor

    return cumulative_factor_by_date


def build_total_return_series(
    adjusted_closes: list[tuple[date, float]],
    dividend_by_date: dict[date, float],
) -> list[tuple[date, float]]:
    series: list[tuple[date, float]] = []
    for index in range(1, len(adjusted_closes)):
        previous = adjusted_closes[index - 1][1]
        current_date, current = adjusted_closes[index]
        if previous <= 0:
            continue
        cash_dividend = dividend_by_date.get(current_date, 0.0)
        series.append((current_date, ((current + cash_dividend) / previous) - 1))
    return series


def parse_action_ratio(row: dict[str, str], numerator_key: str, denominator_key: str) -> tuple[Decimal | None, Decimal | None]:
    numerator = row.get(numerator_key)
    denominator = row.get(denominator_key)
    if not numerator or not denominator:
        return None, None
    return Decimal(str(numerator)), Decimal(str(denominator))
