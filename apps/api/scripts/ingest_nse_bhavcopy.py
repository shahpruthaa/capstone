import argparse
from datetime import date
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.ingestion.nse_bhavcopy import ingest_nse_bhavcopy_range


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NSE CM bhavcopy data into PostgreSQL.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format.")
    parser.add_argument("--series", nargs="*", default=["EQ"], help="Series filter, default EQ.")
    parser.add_argument("--dry-run", action="store_true", help="Download and parse without committing to the database.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start_date = date.fromisoformat(args.start_date)
    end_date = date.fromisoformat(args.end_date) if args.end_date else None
    started = monotonic()

    def render_progress(update: dict[str, object]) -> None:
        completed_days = int(update["completed_days"])
        total_days = max(int(update["total_days"]), 1)
        current_date = update["current_date"]
        records_processed = int(update["records_processed"])
        records_inserted = int(update["records_inserted"])
        records_updated = int(update["records_updated"])
        percent = int((completed_days / total_days) * 100)
        bar_width = 28
        filled = int((completed_days / total_days) * bar_width)
        bar = "#" * filled + "-" * (bar_width - filled)
        elapsed = monotonic() - started
        rate = completed_days / elapsed if elapsed > 0 else 0
        remaining = (total_days - completed_days) / rate if rate > 0 else 0
        sys.stdout.write(
            "\r"
            f"[{bar}] {percent:>3}% "
            f"{completed_days}/{total_days} days "
            f"| {current_date} "
            f"| processed={records_processed} inserted={records_inserted} updated={records_updated} "
            f"| eta~{remaining:5.0f}s"
        )
        sys.stdout.flush()

    with SessionLocal() as db:
        summary = ingest_nse_bhavcopy_range(
            db=db,
            start_date=start_date,
            end_date=end_date,
            include_series=args.series,
            dry_run=args.dry_run,
            progress_callback=render_progress,
        )

    print()
    print(f"Run ID: {summary.run_id}")
    print(f"Status: {summary.status}")
    print(f"Processed: {summary.records_processed}")
    print(f"Inserted: {summary.records_inserted}")
    print(f"Updated: {summary.records_updated}")
    for note in summary.notes:
        print(f"- {note}")


if __name__ == "__main__":
    main()
