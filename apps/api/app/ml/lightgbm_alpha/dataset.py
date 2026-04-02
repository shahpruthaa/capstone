from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.ml.lightgbm_alpha.features import compute_snapshot_features
from app.models.daily_bar import DailyBar
from app.models.instrument import Instrument
from app.services.corporate_actions import load_corporate_actions
from app.services.db_quant_engine import RISK_MODE_UNIVERSES, load_snapshots


LOOKBACK_DAYS_TRADING = 252
HORIZON_DAYS_TRADING = 21


# Keep feature names aligned with `compute_snapshot_features()` + predictor manifest.
NUMERIC_FEATURES: list[str] = [
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "ret_252d",
    "vol_21d",
    "vol_63d",
    "vol_126d",
    "downside_vol_21d",
    "downside_vol_63d",
    "downside_vol_126d",
    "max_drawdown_252d",
    "dma_ratio_20",
    "dma_ratio_50",
    "dma_ratio_200",
    "dist_to_52w_high",
    "gap_proxy",
    "range_proxy",
    "avg_traded_value_20d",
    "liquidity_percentile",
    "beta_proxy",
    "sector_relative_momentum",
    "factor_momentum",
    "factor_quality",
    "factor_low_vol",
    "factor_liquidity",
    "factor_sector_strength",
    "factor_size",
    "factor_beta",
]

CATEGORICAL_FEATURES: list[str] = ["sector_cat", "market_cap_bucket_cat"]
FEATURE_ORDER: list[str] = NUMERIC_FEATURES + CATEGORICAL_FEATURES


@dataclass(frozen=True)
class DatasetBuildResult:
    df: pd.DataFrame
    feature_order: list[str]
    numeric_features: list[str]
    categorical_features: list[str]
    sector_mapping: dict[str, int]
    market_cap_bucket_mapping: dict[str, int]


def _zscore_winsorize_per_date(rows: list[dict[str, Any]], numeric_features: list[str]) -> list[dict[str, float]]:
    import numpy as np

    out: list[dict[str, float]] = []
    for f in numeric_features:
        values = [float(r.get(f, 0.0)) for r in rows]
        p1 = float(np.quantile(values, 0.01))
        p99 = float(np.quantile(values, 0.99))
        clipped = [min(p99, max(p1, v)) for v in values]
        mean = float(np.mean(clipped))
        std = float(np.std(clipped, ddof=1)) if len(clipped) > 1 else 0.0
        if std <= 1e-12:
            std = 1.0
        for i, r in enumerate(rows):
            r[f] = (clipped[i] - mean) / std

    for r in rows:
        out.append({k: float(v) for k, v in r.items() if k in numeric_features})
    return out


def _get_benchmark_symbol(db: Session) -> str:
    preferred = ["NIFTYBEES", "JUNIORBEES", "LIQUIDBEES", "GOLDBEES"]
    q = select(Instrument.symbol).where(Instrument.symbol.in_(preferred))
    symbols = [row[0] for row in db.execute(q).all()]
    for p in preferred:
        if p in symbols:
            return p
    # Fallback: any equity/ETF in the DB.
    row = db.execute(select(Instrument.symbol).limit(1)).first()
    if row and row[0]:
        return str(row[0])
    return "NIFTYBEES"


def build_lightgbm_ml_dataset(
    db: Session,
    *,
    start_date: date,
    end_date: date,
    max_symbols: int | None = 50,
    benchmark_symbol: str | None = None,
) -> DatasetBuildResult:
    """
    Build a supervised dataset where each row is:
      (symbol, decision_date) -> features at decision_date, label = 21-trading-day forward return.

    Notes:
    - This uses `load_snapshots()` for split/bonus-adjusted history + factor z-scores so that
      training/inference align with the current rule engine.
    - Corporate actions are used when computing the forward label (dividends reinvested notion).
    """
    benchmark_symbol = benchmark_symbol or _get_benchmark_symbol(db)

    # Select universe by avg daily traded value — top liquid stocks only.
    liquidity_stmt = (
        select(
            Instrument.symbol,
            Instrument.sector,
            Instrument.market_cap_bucket,
            func.avg(DailyBar.total_traded_value).label("avg_value"),
            func.count(DailyBar.id).label("day_count"),
        )
        .join(DailyBar, DailyBar.instrument_id == Instrument.id)
        .where(
            Instrument.instrument_type == "EQUITY",
            Instrument.is_active.is_(True),
            DailyBar.total_traded_value > 0,
        )
        .group_by(Instrument.symbol, Instrument.sector, Instrument.market_cap_bucket)
        .having(func.count(DailyBar.id) >= 200)
        .order_by(func.avg(DailyBar.total_traded_value).desc())
    )
    if max_symbols is not None:
      liquidity_stmt = liquidity_stmt.limit(max_symbols)
    universe_rows = db.execute(liquidity_stmt).all()
    universe_symbols = [str(r.symbol) for r in universe_rows]
    if not universe_symbols:
        raise ValueError("No equity instruments available for ML dataset build.")

    sector_mapping: dict[str, int] = {"Unknown": 0}
    market_cap_bucket_mapping: dict[str, int] = {"Unknown": 0}
    for r in universe_rows:
        sector = str(r.sector) if r.sector else "Unknown"
        cap = str(r.market_cap_bucket) if r.market_cap_bucket else "Unknown"
        if sector not in sector_mapping:
            sector_mapping[sector] = len(sector_mapping)
        if cap not in market_cap_bucket_mapping:
            market_cap_bucket_mapping[cap] = len(market_cap_bucket_mapping)

    # Trading calendar from benchmark symbol.
    calendar_start = start_date - timedelta(days=650)
    calendar_end = end_date + timedelta(days=40)
    cal_q = (
        select(DailyBar.trade_date)
        .join(Instrument, DailyBar.instrument_id == Instrument.id)
        .where(Instrument.symbol == benchmark_symbol, DailyBar.trade_date >= calendar_start, DailyBar.trade_date <= calendar_end)
        .order_by(DailyBar.trade_date.asc())
    )
    cal_dates = [row[0] for row in db.execute(cal_q).all()]
    if len(cal_dates) < (LOOKBACK_DAYS_TRADING + HORIZON_DAYS_TRADING + 2):
        raise ValueError("Not enough benchmark trading history to build ML dataset.")

    # Weekly decision dates: last trading day of each week (Friday or last available).
    week_last: dict[tuple[int, int], date] = {}
    for d in cal_dates:
        key = (d.isocalendar()[0], d.isocalendar()[1])
        week_last[key] = d
    decision_dates = sorted([d for (y, w), d in week_last.items() if start_date <= d <= end_date])

    # Ensure lookback + forward windows exist (in trading-day index terms).
    cal_index = {d: i for i, d in enumerate(cal_dates)}
    eligible_decision_dates: list[date] = []
    for d in decision_dates:
        idx = cal_index.get(d)
        if idx is None:
            continue
        if idx - LOOKBACK_DAYS_TRADING < 0:
            continue
        if idx + HORIZON_DAYS_TRADING >= len(cal_dates):
            continue
        eligible_decision_dates.append(d)

    if not eligible_decision_dates:
        raise ValueError("No eligible weekly decision dates found for ML dataset build.")

    # Preload corporate actions for forward label.
    max_label_end = eligible_decision_dates[-1] + timedelta(days=45)
    corporate_actions_map = load_corporate_actions(db, symbols=universe_symbols, end_date=max_label_end)

    rows_out: list[dict[str, Any]] = []
    for decision_date in eligible_decision_dates:
        # Snapshots up to decision_date (past window only).
        snapshots = load_snapshots(
            db,
            as_of_date=decision_date,
            symbols=universe_symbols,
            lookback_days=500,
            min_history=LOOKBACK_DAYS_TRADING + 1,
        )
        if not snapshots:
            continue

        snapshot_map = {s.symbol: s for s in snapshots}
        idx = cal_index[decision_date]
        future_dates = cal_dates[idx : idx + (HORIZON_DAYS_TRADING + 1)]  # includes decision_date itself
        label_end_date = future_dates[-1]

        # Cross-sectional raw feature extraction.
        raw_feature_rows: list[dict[str, Any]] = []
        symbol_order: list[str] = []
        labels: dict[str, float] = {}

        # Precompute liquidity percentile inputs from avg_traded_value.
        avg_tov_list: list[tuple[str, float]] = []

        for sym, s in snapshot_map.items():
            # Require future bars exist for forward label.
            daily_bars_q = (
                select(DailyBar.trade_date, DailyBar.close_price)
                .join(Instrument, DailyBar.instrument_id == Instrument.id)
                .where(Instrument.symbol == sym, DailyBar.trade_date.in_(future_dates))
            )
            bar_rows = db.execute(daily_bars_q).all()
            if len(bar_rows) != len(future_dates):
                continue
            bar_map = {r.trade_date: float(r.close_price) for r in bar_rows}

            # Compute forward total-return index over the 21-trading-day horizon.
            # Adjust close series using corporate actions in the forward window.
            closes_future = [(d, bar_map[d]) for d in future_dates]
            from app.services.corporate_actions import adjust_close_series, build_total_return_series

            adj_closes_future, dividend_by_date = adjust_close_series(closes_future, corporate_actions_map.get(sym, []))
            total_return_returns_future = build_total_return_series(adj_closes_future, dividend_by_date)

            # total_return_index construction.
            from app.ml.lightgbm_alpha.features import compute_total_return_index

            idx_series = compute_total_return_index(adj_closes_future, total_return_returns_future)
            if len(idx_series) < 2:
                continue
            label = idx_series[-1] / max(idx_series[0], 1e-12) - 1.0
            # Clip to training target range.
            label = float(max(-0.30, min(0.30, label)))

            feat = compute_snapshot_features(s)
            # liquidity_percentile is added later after we have the cross-section.
            raw_feature_rows.append(feat)
            symbol_order.append(sym)
            labels[sym] = label

            avg_tov = float(feat.get("avg_traded_value_20d", 0.0))
            avg_tov_list.append((sym, avg_tov))

        if len(raw_feature_rows) < 8:
            continue

        # Liquidity percentile across this decision date.
        avg_tov_list_sorted = sorted(avg_tov_list, key=lambda x: x[1])
        sym_to_rank = {sym: rank for rank, (sym, _) in enumerate(avg_tov_list_sorted)}
        n = max(1, len(avg_tov_list_sorted))
        for i, sym in enumerate(symbol_order):
            rank = sym_to_rank.get(sym, 0)
            raw_feature_rows[i]["liquidity_percentile"] = float(rank / max(n - 1, 1))

        # Categorical encoding.
        for i, sym in enumerate(symbol_order):
            s = snapshot_map[sym]
            sector = s.sector or "Unknown"
            cap_bucket = s.market_cap_bucket or "Unknown"
            raw_feature_rows[i]["sector_cat"] = float(sector_mapping.get(sector, 0))
            raw_feature_rows[i]["market_cap_bucket_cat"] = float(market_cap_bucket_mapping.get(cap_bucket, 0))

        # Winsorize + zscore numeric features per decision date.
        transformed_numeric = _zscore_winsorize_per_date(raw_feature_rows, NUMERIC_FEATURES)

        # Attach label and metadata.
        for i, sym in enumerate(symbol_order):
            row = {"symbol": sym, "decision_date": decision_date, "target_21d": labels[sym]}
            row.update({f: transformed_numeric[i][f] for f in NUMERIC_FEATURES})
            row["sector_cat"] = float(raw_feature_rows[i]["sector_cat"])
            row["market_cap_bucket_cat"] = float(raw_feature_rows[i]["market_cap_bucket_cat"])
            rows_out.append(row)

    df = pd.DataFrame(rows_out)
    if df.empty:
        raise ValueError("ML dataset build produced no rows.")

    return DatasetBuildResult(
        df=df,
        feature_order=FEATURE_ORDER,
        numeric_features=NUMERIC_FEATURES,
        categorical_features=CATEGORICAL_FEATURES,
        sector_mapping=sector_mapping,
        market_cap_bucket_mapping=market_cap_bucket_mapping,
    )
