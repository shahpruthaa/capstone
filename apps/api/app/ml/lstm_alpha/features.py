from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.daily_bar import DailyBar
from app.models.instrument import Instrument

logger = logging.getLogger(__name__)
LOOKBACK_DAYS = 20
FORWARD_DAYS = 21


def _get_daily_bars_for_symbol(db: Session, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    query = (
        select(DailyBar.trade_date, DailyBar.open_price, DailyBar.high_price,
               DailyBar.low_price, DailyBar.close_price, DailyBar.total_traded_qty)
        .join(Instrument, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol == symbol)
        .where(DailyBar.trade_date >= start_date)
        .where(DailyBar.trade_date <= end_date)
        .order_by(DailyBar.trade_date)
    )
    rows = db.execute(query).all()
    if not rows:
        return pd.DataFrame()
    data = [{
        "trade_date": r.trade_date,
        "open": float(r.open_price),
        "high": float(r.high_price),
        "low": float(r.low_price),
        "close": float(r.close_price),
        "volume": float(r.total_traded_qty) if r.total_traded_qty else 0.0,
    } for r in rows]
    return pd.DataFrame(data).sort_values("trade_date").reset_index(drop=True)


def _build_sequences_for_symbol(df: pd.DataFrame, decision_date: date) -> list[dict[str, Any]]:
    if len(df) < LOOKBACK_DAYS + FORWARD_DAYS:
        return []
    df = df.sort_values("trade_date").reset_index(drop=True)
    df["return"] = df["close"].pct_change().fillna(0.0)
    df["high_low_ratio"] = df["high"] / (df["low"] + 1e-8)

    # Find the index of decision_date or the last date before it
    eligible = df[df["trade_date"] <= decision_date]
    if len(eligible) < LOOKBACK_DAYS:
        return []
    end_idx = eligible.index[-1]
    if end_idx + FORWARD_DAYS >= len(df):
        return []
    start_idx = end_idx - LOOKBACK_DAYS + 1
    if start_idx < 0:
        return []

    window = df.iloc[start_idx:end_idx + 1]
    target_idx = end_idx + FORWARD_DAYS
    seq_start_close = window["close"].iloc[0]
    target_close = df.iloc[target_idx]["close"]
    target_21d = float(np.clip((target_close - seq_start_close) / (seq_start_close + 1e-8), -0.30, 0.30))

    return [{
        "close_prices": window["close"].values.astype(np.float32),
        "volumes": window["volume"].values.astype(np.float32),
        "returns": window["return"].values.astype(np.float32),
        "high_low_ratios": window["high_low_ratio"].values.astype(np.float32),
        "target_21d": target_21d,
        "sequence_end_date": decision_date,
    }]


def build_lstm_dataset_from_db(db: Session, symbols: list[str], decision_dates: list[date]) -> pd.DataFrame:
    start_date = min(decision_dates) - timedelta(days=60)
    end_date = max(decision_dates) + timedelta(days=FORWARD_DAYS + 10)
    all_sequences = []
    for symbol in symbols:
        df = _get_daily_bars_for_symbol(db, symbol, start_date, end_date)
        if df.empty:
            continue
        for decision_date in decision_dates:
            seqs = _build_sequences_for_symbol(df, decision_date)
            for seq in seqs:
                row = {"symbol": symbol, "decision_date": decision_date}
                for i in range(LOOKBACK_DAYS):
                    row[f"close_{i}"] = seq["close_prices"][i]
                    row[f"volume_{i}"] = seq["volumes"][i]
                    row[f"return_{i}"] = seq["returns"][i]
                    row[f"high_low_ratio_{i}"] = seq["high_low_ratios"][i]
                row["target_21d"] = seq["target_21d"]
                all_sequences.append(row)
    if not all_sequences:
        raise ValueError("No LSTM sequences built.")
    df_out = pd.DataFrame(all_sequences)
    logger.info(f"Built LSTM dataset: {len(df_out)} sequences from {len(symbols)} symbols")
    return df_out


def normalize_lstm_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, tuple[float, float]]]:
    stats: dict[str, tuple[float, float]] = {}
    out = df.copy()
    feature_cols = [c for c in df.columns if any(
        c.startswith(p) for p in ("close_", "volume_", "return_", "high_low_ratio_")
    )]
    for col in feature_cols:
        mean_val = float(out[col].mean())
        std_val = float(out[col].std())
        if std_val < 1e-8:
            std_val = 1.0
        out[col] = (out[col] - mean_val) / std_val
        stats[col] = (mean_val, std_val)
    return out, stats
