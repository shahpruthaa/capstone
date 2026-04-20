from __future__ import annotations
import logging
from datetime import date

logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed — auto-ingestion disabled")
        return

    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        _ingest_latest,
        CronTrigger(hour=16, minute=15, timezone="Asia/Kolkata"),
        id="daily_ingest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Auto-ingestion scheduler started — runs daily at 16:15 IST")


def _ingest_latest() -> None:
    from app.db.session import SessionLocal
    from app.ingestion.nse_bhavcopy import ingest_bhavcopy_range

    today = date.today()
    if today.weekday() >= 5:
        logger.info(f"Scheduler: skipping {today} (weekend)")
        return

    logger.info(f"Scheduler: ingesting bhavcopy for {today}")
    db = SessionLocal()
    try:
        result = ingest_bhavcopy_range(db, start_date=today, end_date=today)
        logger.info(f"Scheduler: ingested {result.get('inserted', 0)} records for {today}")
    except Exception as e:
        logger.error(f"Scheduler: ingestion failed for {today}: {e}")
    finally:
        db.close()
