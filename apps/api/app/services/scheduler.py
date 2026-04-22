from __future__ import annotations

import logging

from app.core.config import settings
from app.services.market_calendar import latest_completed_trading_day


logger = logging.getLogger(__name__)
_SCHEDULER = None


def start_scheduler() -> None:
    global _SCHEDULER

    if not settings.scheduler_enabled:
        logger.info("Auto-ingestion scheduler disabled via APP_SCHEDULER_ENABLED")
        return
    if _SCHEDULER is not None:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed - auto-ingestion disabled")
        return

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        _ingest_latest,
        CronTrigger(hour=19, minute=0, timezone="Asia/Kolkata"),
        id="nightly_nse_bhavcopy_ingest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    _SCHEDULER = scheduler
    logger.info("Auto-ingestion scheduler started - runs nightly at 19:00 IST")


def stop_scheduler() -> None:
    global _SCHEDULER

    if _SCHEDULER is None:
        return
    _SCHEDULER.shutdown(wait=False)
    _SCHEDULER = None


def _ingest_latest() -> None:
    from app.db.session import SessionLocal
    from app.ingestion.nse_bhavcopy import ingest_nse_bhavcopy_range

    trade_date = latest_completed_trading_day()
    logger.info("Scheduler: ingesting bhavcopy for %s", trade_date)
    db = SessionLocal()
    try:
        result = ingest_nse_bhavcopy_range(db=db, start_date=trade_date, end_date=trade_date)
        logger.info(
            "Scheduler: completed bhavcopy ingestion for %s with status=%s inserted=%s updated=%s",
            trade_date,
            result.status,
            result.records_inserted,
            result.records_updated,
        )
    except Exception as exc:
        logger.error("Scheduler: ingestion failed for %s: %s", trade_date, exc, exc_info=True)
    finally:
        db.close()
