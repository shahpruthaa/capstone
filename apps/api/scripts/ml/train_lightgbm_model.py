from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from app.ml.lightgbm_alpha.train import train_lightgbm_regressor_with_walk_forward


def _resolve_walk_forward_windows(decision_dates_count: int) -> tuple[int, int, int, int]:
    preferred = (24, 6, 6, 1)
    compressed = (12, 3, 3, 1)
    minimal = (8, 2, 2, 1)
    bootstrap = (6, 2, 2, 1)

    if decision_dates_count >= sum(preferred):
        return preferred
    if decision_dates_count >= sum(compressed):
        return compressed
    if decision_dates_count >= sum(minimal):
        return minimal
    if decision_dates_count >= sum(bootstrap):
        return bootstrap
    raise ValueError(
        f"Not enough monthly decision dates to train LightGBM (found={decision_dates_count}, need at least {sum(bootstrap)})."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-csv", required=True, help="Path to ml_dataset.csv")
    parser.add_argument("--dataset-manifest-json", required=True, help="Path to dataset_manifest.json")
    parser.add_argument("--artifact-dir", default="artifacts/models/lightgbm_v1", help="Where to write model artifacts")
    parser.add_argument("--model-version", default=None, help="Model version string")
    parser.add_argument("--initial-train-decision-dates", type=int, default=None)
    parser.add_argument("--val-decision-dates", type=int, default=None)
    parser.add_argument("--test-decision-dates", type=int, default=None)
    parser.add_argument("--embargo-decision-dates", type=int, default=1)
    args = parser.parse_args()

    dataset_manifest_path = Path(args.dataset_manifest_json)
    dataset_path = Path(args.dataset_csv)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    feature_order: list[str] = manifest["feature_order"]
    numeric_features: list[str] = manifest["numeric_features"]
    sector_mapping: dict[str, int] = manifest["sector_mapping"]
    market_cap_bucket_mapping: dict[str, int] = manifest["market_cap_bucket_mapping"]

    df = pd.read_csv(dataset_path)
    # Ensure date parsing for deterministic ordering.
    df["decision_date"] = pd.to_datetime(df["decision_date"]).dt.date
    decision_dates_count = len(sorted(df["decision_date"].unique()))
    bootstrap_mode = decision_dates_count < 12

    model_version = args.model_version or f"lightgbm_v1_{date.today().isoformat()}"
    if (
        args.initial_train_decision_dates is not None
        and args.val_decision_dates is not None
        and args.test_decision_dates is not None
    ):
        walk_forward_windows = (
            args.initial_train_decision_dates,
            args.val_decision_dates,
            args.test_decision_dates,
            args.embargo_decision_dates,
        )
    else:
        walk_forward_windows = _resolve_walk_forward_windows(decision_dates_count)

    if bootstrap_mode:
        model_hyperparams = {
            "objective": "huber",
            "learning_rate": 0.05,
            "num_leaves": 15,
            "n_estimators": 300,
            "min_child_samples": 10,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
        }
        training_mode = "bootstrap"
    else:
        model_hyperparams = {
            "objective": "huber",
            "learning_rate": 0.03,
            "num_leaves": 31,
            "n_estimators": 600,
            "min_child_samples": 50,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
        }
        training_mode = "standard"

    train_lightgbm_regressor_with_walk_forward(
        df,
        feature_order=feature_order,
        numeric_features=numeric_features,
        target_col="target_21d",
        decision_date_col="decision_date",
        prediction_horizon_days=21,
        sector_mapping=sector_mapping,
        market_cap_bucket_mapping=market_cap_bucket_mapping,
        artifact_dir=str(artifact_dir),
        model_version=model_version,
        model_hyperparams=model_hyperparams,
        initial_train_decision_dates=walk_forward_windows[0],
        val_decision_dates=walk_forward_windows[1],
        test_decision_dates=walk_forward_windows[2],
        embargo_decision_dates=walk_forward_windows[3],
        allow_negative_ic=bootstrap_mode,
        training_mode=training_mode,
    )


if __name__ == "__main__":
    main()
