import argparse
from datetime import date
from pathlib import Path
import sys

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

    with SessionLocal() as db:
        summary = ingest_nse_bhavcopy_range(
            db=db,
            start_date=start_date,
            end_date=end_date,
            include_series=args.series,
            dry_run=args.dry_run,
        )

    print(f"Run ID: {summary.run_id}")
    print(f"Status: {summary.status}")
    print(f"Processed: {summary.records_processed}")
    print(f"Inserted: {summary.records_inserted}")
    print(f"Updated: {summary.records_updated}")
    for note in summary.notes:
        print(f"- {note}")


if __name__ == "__main__":
    main()
