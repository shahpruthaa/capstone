from __future__ import annotations

import logging

from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.ingestion.nse_bhavcopy import discover_cached_bhavcopy_archives, ingest_cached_nse_bhavcopy_archives
from app.models import (  # noqa: F401
    backtest_run,
    corporate_action,
    daily_bar,
    fundamental_snapshot,
    generated_portfolio_run,
    ingestion_run,
    institutional_flow,
    instrument,
    market_regime_snapshot,
    options_snapshot,
)
from app.models.daily_bar import DailyBar


logger = logging.getLogger(__name__)


def bootstrap_local_state() -> dict[str, object]:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        bar_count = int(db.execute(select(func.count(DailyBar.id))).scalar_one() or 0)
        if bar_count > 0:
            return {"bootstrapped": False, "reason": "market_data_present", "daily_bar_count": bar_count}

        cached_archives = discover_cached_bhavcopy_archives()
        if not cached_archives:
            return {"bootstrapped": False, "reason": "no_cached_archives", "daily_bar_count": 0}

        summary = ingest_cached_nse_bhavcopy_archives(db, include_series=("EQ",))
        logger.info(
            "Bootstrapped local cached bhavcopy data: status=%s processed=%s inserted=%s updated=%s",
            summary.status,
            summary.records_processed,
            summary.records_inserted,
            summary.records_updated,
        )
        return {
            "bootstrapped": True,
            "reason": "ingested_cached_archives",
            "status": summary.status,
            "daily_bar_count": summary.records_inserted + summary.records_updated,
            "notes": summary.notes[-5:],
        }
