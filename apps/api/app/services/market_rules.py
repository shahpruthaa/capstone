from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class EquityFeeSchedule:
    effective_from: date
    brokerage_rate: float
    max_brokerage_per_order: float
    stt_buy_rate: float
    stt_sell_rate: float
    exchange_txn_rate: float
    sebi_fee_rate: float
    stamp_duty_buy_rate: float
    gst_rate: float
    notes: str


@dataclass(frozen=True)
class CapitalGainsTaxSchedule:
    effective_from: date
    stcg_rate: float
    ltcg_rate: float
    ltcg_exemption: float
    cess_rate: float
    notes: str


EQUITY_FEE_SCHEDULES = [
    EquityFeeSchedule(
        effective_from=date(2020, 7, 1),
        brokerage_rate=0.0003,
        max_brokerage_per_order=20.0,
        stt_buy_rate=0.001,
        stt_sell_rate=0.001,
        exchange_txn_rate=0.0000297,
        sebi_fee_rate=0.000001,
        stamp_duty_buy_rate=0.00015,
        gst_rate=0.18,
        notes="Cash-delivery equity fee schedule with capped brokerage and statutory levies.",
    ),
    EquityFeeSchedule(
        effective_from=date(2024, 7, 23),
        brokerage_rate=0.0003,
        max_brokerage_per_order=20.0,
        stt_buy_rate=0.001,
        stt_sell_rate=0.001,
        exchange_txn_rate=0.0000297,
        sebi_fee_rate=0.000001,
        stamp_duty_buy_rate=0.00015,
        gst_rate=0.18,
        notes="Versioned cash-equity schedule retained by effective date so historical replays can select the correct rule set.",
    ),
]

CAPITAL_GAINS_TAX_SCHEDULES = [
    CapitalGainsTaxSchedule(
        effective_from=date(2020, 7, 1),
        stcg_rate=0.15,
        ltcg_rate=0.10,
        ltcg_exemption=100000.0,
        cess_rate=0.04,
        notes="Pre-Budget-2024 listed-equity capital gains schedule.",
    ),
    CapitalGainsTaxSchedule(
        effective_from=date(2024, 7, 23),
        stcg_rate=0.20,
        ltcg_rate=0.125,
        ltcg_exemption=125000.0,
        cess_rate=0.04,
        notes="Budget-2024 listed-equity capital gains schedule.",
    ),
]


def resolve_equity_fee_schedule(trade_date: date) -> EquityFeeSchedule:
    active = EQUITY_FEE_SCHEDULES[0]
    for schedule in EQUITY_FEE_SCHEDULES:
        if schedule.effective_from <= trade_date:
            active = schedule
    return active


def resolve_capital_gains_tax_schedule(trade_date: date) -> CapitalGainsTaxSchedule:
    active = CAPITAL_GAINS_TAX_SCHEDULES[0]
    for schedule in CAPITAL_GAINS_TAX_SCHEDULES:
        if schedule.effective_from <= trade_date:
            active = schedule
    return active


def financial_year_for_trade_date(trade_date: date) -> str:
    if trade_date.month >= 4:
        return f"{trade_date.year}-{str(trade_date.year + 1)[-2:]}"
    return f"{trade_date.year - 1}-{str(trade_date.year)[-2:]}"
