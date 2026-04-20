from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_bar import DailyBar
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.services.db_quant_engine import Snapshot, load_snapshots
from app.ingestion.common import finish_ingestion_run, start_ingestion_run


def ingest_market_regime_range(
    db: Session,
    *,
    start_date: date,
    end_date: date | None = None,
    dry_run: bool = False,
) -> Any:
    effective_end = end_date or start_date
    run, started_at = start_ingestion_run(db, source="derived", dataset="market_regime")
    notes: list[str] = []
    processed = inserted = updated = 0
    status = "completed"

    try:
        trade_dates = db.execute(
            select(DailyBar.trade_date)
            .where(DailyBar.trade_date >= start_date, DailyBar.trade_date <= effective_end)
            .distinct()
            .order_by(DailyBar.trade_date)
        ).scalars().all()

        if not trade_dates:
            notes.append("No trade dates found in the requested range.")

        for trade_date in trade_dates:
            derived = build_market_regime_snapshot(db, trade_date=trade_date)
            if derived is None:
                notes.append(f"{trade_date.isoformat()}: skipped due to insufficient history.")
                continue

            record = db.get(MarketRegimeSnapshot, {"regime_date": trade_date})
            is_new = record is None
            if record is None:
                record = MarketRegimeSnapshot(regime_date=trade_date, regime=derived["regime"])

            record.regime = derived["regime"]
            record.regime_confidence = derived["regime_confidence"]
            record.nifty_50_level = derived["nifty_50_level"]
            record.india_vix = derived["india_vix"]
            record.advance_decline_ratio = derived["advance_decline_ratio"]
            record.nifty_50d_sma = derived["nifty_50d_sma"]
            record.nifty_200d_sma = derived["nifty_200d_sma"]
            record.stocks_above_50d_sma_pct = derived["stocks_above_50d_sma_pct"]
            record.stocks_above_200d_sma_pct = derived["stocks_above_200d_sma_pct"]
            record.source = "derived_daily_bars"
            db.add(record)

            processed += 1
            inserted += 1 if is_new else 0
            updated += 0 if is_new else 1

        notes.append(f"Market regime snapshots generated for {processed} trade dates.")
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        notes.append(f"Market regime ingestion failed: {exc}")

    return finish_ingestion_run(
        db,
        run=run,
        started_at=started_at,
        source="derived",
        dataset="market_regime",
        status=status,
        processed=processed,
        inserted=inserted,
        updated=updated,
        notes=notes,
        dry_run=dry_run,
    )


def build_market_regime_snapshot(db: Session, *, trade_date: date) -> dict[str, Any] | None:
    snapshots = load_snapshots(db, as_of_date=trade_date, min_history=50)
    if len(snapshots) < 5:
        return None

    benchmark = next((snapshot for snapshot in snapshots if snapshot.symbol == "NIFTYBEES"), None)
    reference = benchmark or max(snapshots, key=lambda snapshot: snapshot.avg_traded_value, default=None)
    if reference is None:
        return None

    closes = [price for _, price in reference.adjusted_closes]
    if len(closes) < 50:
        return None

    nifty_level = float(reference.latest_price)
    sma50 = _sma(closes, 50)
    sma200 = _sma(closes, 200)
    india_vix_snapshot = next((snapshot for snapshot in snapshots if snapshot.symbol == "INDIAVIX"), None)
    india_vix = float(india_vix_snapshot.latest_price) if india_vix_snapshot is not None else None

    equities = [snapshot for snapshot in snapshots if snapshot.instrument_type != "ETF"]
    above_50 = above_200 = eligible_50 = eligible_200 = 0
    advances = declines = 0
    for snapshot in equities:
        series = [price for _, price in snapshot.adjusted_closes]
        if len(series) >= 2:
            if series[-1] > series[-2]:
                advances += 1
            elif series[-1] < series[-2]:
                declines += 1
        if len(series) >= 50:
            eligible_50 += 1
            above_50 += int(series[-1] > _sma(series, 50))
        if len(series) >= 200:
            eligible_200 += 1
            above_200 += int(series[-1] > _sma(series, 200))

    breadth_50 = (above_50 / eligible_50 * 100.0) if eligible_50 else 0.0
    breadth_200 = (above_200 / eligible_200 * 100.0) if eligible_200 else 0.0
    advance_decline_ratio = (advances / declines) if declines > 0 else (float(advances) if advances > 0 else 1.0)

    regime, confidence = _classify_regime(
        level=nifty_level,
        sma50=sma50,
        sma200=sma200,
        breadth_50=breadth_50,
        breadth_200=breadth_200,
        india_vix=india_vix,
    )

    return {
        "regime": regime,
        "regime_confidence": confidence,
        "nifty_50_level": round(nifty_level, 2),
        "india_vix": round(india_vix, 2) if india_vix is not None else None,
        "advance_decline_ratio": round(advance_decline_ratio, 4),
        "nifty_50d_sma": round(sma50, 2),
        "nifty_200d_sma": round(sma200, 2),
        "stocks_above_50d_sma_pct": round(breadth_50, 2),
        "stocks_above_200d_sma_pct": round(breadth_200, 2),
    }


def _classify_regime(
    *,
    level: float,
    sma50: float,
    sma200: float,
    breadth_50: float,
    breadth_200: float,
    india_vix: float | None,
) -> tuple[str, float]:
    bull_score = 0
    bear_score = 0
    signal_count = 4

    if level > sma200:
        bull_score += 1
    else:
        bear_score += 1

    if sma50 > sma200:
        bull_score += 1
    else:
        bear_score += 1

    if breadth_50 > 60:
        bull_score += 1
    elif breadth_50 < 40:
        bear_score += 1

    if breadth_200 > 55:
        bull_score += 1
    elif breadth_200 < 45:
        bear_score += 1

    if india_vix is not None:
        signal_count += 1
        if india_vix < 16:
            bull_score += 1
        elif india_vix > 22:
            bear_score += 1

    if bull_score >= max(3, signal_count - 1):
        return "bull", round(bull_score / signal_count, 2)
    if bear_score >= max(3, signal_count - 1):
        return "bear", round(bear_score / signal_count, 2)
    return "sideways", round(max(bull_score, bear_score) / signal_count, 2)


def _sma(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    if len(values) < window:
        return sum(values) / len(values)
    return sum(values[-window:]) / window
