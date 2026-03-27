from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from app.db.session import SessionLocal
from app.ml.lightgbm_alpha.dataset import build_lightgbm_ml_dataset


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--max-symbols", type=int, default=50)
    parser.add_argument("--benchmark-symbol", type=str, default=None)
    parser.add_argument("--out-dir", type=str, default="artifacts/datasets/lightgbm_v1")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = out_dir / "ml_dataset.csv"
    dataset_manifest_path = out_dir / "dataset_manifest.json"

    with SessionLocal() as db:
        result = build_lightgbm_ml_dataset(
            db,
            start_date=_parse_date(args.start_date),
            end_date=_parse_date(args.end_date),
            max_symbols=args.max_symbols,
            benchmark_symbol=args.benchmark_symbol,
        )

    # Save dataset.
    result.df.to_csv(dataset_path, index=False)

    # Save manifest.
    import json

    dataset_manifest = {
        "feature_order": result.feature_order,
        "numeric_features": result.numeric_features,
        "categorical_features": result.categorical_features,
        "sector_mapping": result.sector_mapping,
        "market_cap_bucket_mapping": result.market_cap_bucket_mapping,
    }
    dataset_manifest_path.write_text(json.dumps(dataset_manifest, indent=2), encoding="utf-8")

    print(f"Saved dataset: {dataset_path}")
    print(f"Saved dataset manifest: {dataset_manifest_path}")


if __name__ == "__main__":
    main()
