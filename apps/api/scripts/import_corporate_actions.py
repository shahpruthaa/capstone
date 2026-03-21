from __future__ import annotations

import csv
import sys
from argparse import ArgumentParser
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.corporate_action import CorporateAction
from app.models.instrument import Instrument


def main() -> None:
    parser = ArgumentParser(description="Import corporate actions from a CSV file.")
    parser.add_argument("--csv", required=True, help="Path to CSV with symbol,ex_date,action_type and optional ratio/cash columns.")
    parser.add_argument("--source", default="manual_csv", help="Source label to persist.")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    inserted = 0
    updated = 0
    with SessionLocal() as db, csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            symbol = (row.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            instrument = db.execute(select(Instrument).where(Instrument.symbol == symbol)).scalar_one_or_none()
            if instrument is None:
                continue

            ex_date = date.fromisoformat(row["ex_date"].strip())
            action_type = row["action_type"].strip().upper()
            existing = db.execute(
                select(CorporateAction).where(
                    CorporateAction.instrument_id == instrument.id,
                    CorporateAction.ex_date == ex_date,
                    CorporateAction.action_type == action_type,
                )
            ).scalar_one_or_none()

            payload = {
                "instrument_id": instrument.id,
                "ex_date": ex_date,
                "action_type": action_type,
                "ratio_numerator": Decimal(row["ratio_numerator"]) if row.get("ratio_numerator") else None,
                "ratio_denominator": Decimal(row["ratio_denominator"]) if row.get("ratio_denominator") else None,
                "cash_amount": Decimal(row["cash_amount"]) if row.get("cash_amount") else None,
                "description": row.get("description") or None,
                "source": args.source,
            }
            if existing is None:
                db.add(CorporateAction(**payload))
                inserted += 1
            else:
                for key, value in payload.items():
                    setattr(existing, key, value)
                updated += 1

        db.commit()

    print(f"Imported corporate actions from {csv_path}: inserted={inserted}, updated={updated}")


if __name__ == "__main__":
    main()
