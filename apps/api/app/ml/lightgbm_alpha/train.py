from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def _spearman_rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return 0.0
    # Rank without tie-handling (acceptable for capstone; ties are rare in continuous outputs).
    r_true = np.argsort(np.argsort(y_true))
    r_pred = np.argsort(np.argsort(y_pred))
    std_true = np.std(r_true, ddof=1)
    std_pred = np.std(r_pred, ddof=1)
    if std_true <= 1e-12 or std_pred <= 1e-12:
        return 0.0
    return float(np.corrcoef(r_true, r_pred)[0, 1])


def _top_bottom_spread(y_true: np.ndarray, y_pred: np.ndarray, quantile: float = 0.1) -> float:
    n = len(y_true)
    if n < 10:
        return 0.0
    k = max(1, int(n * quantile))
    order = np.argsort(y_pred)
    bottom = order[:k]
    top = order[-k:]
    return float(np.mean(y_true[top]) - np.mean(y_true[bottom]))


@dataclass(frozen=True)
class FoldMetrics:
    fold_name: str
    avg_spearman_ic: float
    avg_top_bottom_spread: float
    rmse: float
    mae: float


def train_lightgbm_regressor_with_walk_forward(
    df: pd.DataFrame,
    *,
    feature_order: list[str],
    numeric_features: list[str],
    target_col: str,
    decision_date_col: str = "decision_date",
    prediction_horizon_days: int,
    sector_mapping: dict[str, int],
    market_cap_bucket_mapping: dict[str, int],
    artifact_dir: str,
    model_version: str,
    model_hyperparams: dict[str, Any],
    initial_train_decision_dates: int = 24,
    val_decision_dates: int = 6,
    test_decision_dates: int = 6,
    embargo_decision_dates: int = 1,
    allow_negative_ic: bool = False,
    training_mode: str = "standard",
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Train + select best model based on out-of-sample average Spearman rank IC.
    Saves LightGBM + manifest artifacts into `artifact_dir`.
    """
    import json
    import os
    import lightgbm as lgb  # type: ignore[import-untyped]
    from pathlib import Path

    if df.empty:
        raise ValueError("Empty dataset.")

    dates_sorted = sorted(df[decision_date_col].unique())
    if len(dates_sorted) < (initial_train_decision_dates + val_decision_dates + test_decision_dates + embargo_decision_dates):
        raise ValueError("Not enough decision dates for walk-forward splits.")

    # Ensure stable deterministic ordering.
    df = df.sort_values(by=[decision_date_col]).reset_index(drop=True)

    X = df[feature_order].copy()
    y = df[target_col].copy()

    # Pre-split indices by decision date for speed.
    date_to_idx = {d: df.index[df[decision_date_col] == d].to_numpy() for d in dates_sorted}

    folds: list[FoldMetrics] = []
    best: tuple[float, Any, dict[str, Any]] | None = None  # (avg_ic, model, extra)

    train_end = initial_train_decision_dates
    fold_num = 0
    while True:
        if train_end + embargo_decision_dates + val_decision_dates + test_decision_dates > len(dates_sorted):
            break

        train_dates = dates_sorted[:train_end]
        val_dates = dates_sorted[train_end + embargo_decision_dates : train_end + embargo_decision_dates + val_decision_dates]
        test_dates = dates_sorted[
            train_end + embargo_decision_dates + val_decision_dates : train_end + embargo_decision_dates + val_decision_dates + test_decision_dates
        ]

        train_idx = np.concatenate([date_to_idx[d] for d in train_dates]) if train_dates else np.array([], dtype=int)
        val_idx = np.concatenate([date_to_idx[d] for d in val_dates]) if val_dates else np.array([], dtype=int)
        test_idx = np.concatenate([date_to_idx[d] for d in test_dates]) if test_dates else np.array([], dtype=int)

        if len(train_idx) == 0 or len(val_idx) == 0 or len(test_idx) == 0:
            train_end += val_decision_dates
            continue

        train_index = df.index[train_idx]
        val_index = df.index[val_idx]
        test_index = df.index[test_idx]

        X_train, y_train = X.loc[train_index], y.loc[train_index]
        X_val, y_val = X.loc[val_index], y.loc[val_index]
        X_test, y_test = X.loc[test_index], y.loc[test_index]

        model = lgb.LGBMRegressor(**model_hyperparams, random_state=random_state)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )

        y_pred_test = model.predict(X_test)

        # Fold-level metrics computed per decision date.
        ic_values: list[float] = []
        spread_values: list[float] = []
        for d in test_dates:
            d_idx = df.index[df[decision_date_col] == d].to_numpy()
            mask = np.isin(test_idx, d_idx)
            if not np.any(mask):
                continue
            # Map to positions in the X_test/y_test arrays.
            # Because indices are global, we re-pick by matching `df.index`.
            test_subset = df.loc[d_idx]
            X_sub = test_subset[feature_order]
            y_true_sub = test_subset[target_col].to_numpy(dtype=float)
            y_pred_sub = model.predict(X_sub)

            ic_values.append(_spearman_rank_ic(y_true_sub, y_pred_sub))
            spread_values.append(_top_bottom_spread(y_true_sub, y_pred_sub))

        avg_ic = float(np.mean(ic_values)) if ic_values else 0.0
        avg_spread = float(np.mean(spread_values)) if spread_values else 0.0
        rmse = float(np.sqrt(np.mean((y_pred_test - y_test) ** 2)))
        mae = float(np.mean(np.abs(y_pred_test - y_test)))

        fold_name = f"fold_{fold_num}_train_upto_{train_dates[-1].isoformat()}_val_start_{val_dates[0].isoformat()}_test_end_{test_dates[-1].isoformat()}"
        fold_metrics = FoldMetrics(
            fold_name=fold_name,
            avg_spearman_ic=avg_ic,
            avg_top_bottom_spread=avg_spread,
            rmse=rmse,
            mae=mae,
        )
        folds.append(fold_metrics)

        extra = {
            "train_dates": [str(d) for d in train_dates],
            "val_dates": [str(d) for d in val_dates],
            "test_dates": [str(d) for d in test_dates],
        }

        if best is None or avg_ic > best[0]:
            best = (avg_ic, model, extra)

        fold_num += 1
        train_end += val_decision_dates

    if best is None:
        raise ValueError("Walk-forward training produced no folds.")

    best_ic, best_model, extra_best = best
    if best_ic < 0 and not allow_negative_ic:
        raise ValueError(f"Rejected model: negative average Spearman IC on held-out folds (best_ic={best_ic:.4f}).")

    # Save artifacts.
    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)

    model_path = artifact_path / "model.txt"
    best_model.booster_.save_model(str(model_path))

    feature_manifest = {
        "model_version": model_version,
        "prediction_horizon_days": prediction_horizon_days,
        "feature_order": feature_order,
        "numeric_features": numeric_features,
        "categorical_features": list(set(feature_order) - set(numeric_features)),
        "sector_mapping": sector_mapping,
        "market_cap_bucket_mapping": market_cap_bucket_mapping,
        "model_hyperparams": model_hyperparams,
    }

    metrics_json = {
        "best_fold": extra_best,
        "folds": [
            {
                "fold_name": f.fold_name,
                "avg_spearman_ic": f.avg_spearman_ic,
                "avg_top_bottom_spread": f.avg_top_bottom_spread,
                "rmse": f.rmse,
                "mae": f.mae,
            }
            for f in folds
        ],
        "best_avg_spearman_ic": best_ic,
        "avg_top_bottom_spread": float(np.mean([f.avg_top_bottom_spread for f in folds])) if folds else 0.0,
        "selection_status": "accepted_with_negative_ic_bootstrap" if best_ic < 0 else "accepted",
        "training_mode": training_mode,
    }

    metadata_json = {
        "trained_on_device": "local_cpu",
        "model_version": model_version,
        "trained_date": str(date.today()),
        "decision_dates_count": len(dates_sorted),
        "training_mode": training_mode,
        "allow_negative_ic": allow_negative_ic,
    }

    with (artifact_path / "feature_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(feature_manifest, f, indent=2)
    with (artifact_path / "metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics_json, f, indent=2)
    with (artifact_path / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata_json, f, indent=2)
    evaluation_report = {
        "model_version": model_version,
        "training_mode": training_mode,
        "prediction_horizon_days": prediction_horizon_days,
        "decision_dates_count": len(dates_sorted),
        "selection_status": metrics_json["selection_status"],
        "validation_summary": {
            "best_avg_spearman_ic": best_ic,
            "avg_top_bottom_spread": metrics_json["avg_top_bottom_spread"],
            "fold_count": len(folds),
        },
        "folds": metrics_json["folds"],
        "feature_count": len(feature_order),
        "feature_order": feature_order,
        "feature_manifest_summary": {
            "numeric_feature_count": len(numeric_features),
            "categorical_feature_count": len(set(feature_order) - set(numeric_features)),
        },
        "acceptance_reason": (
            "Bootstrap artifact accepted for local development despite negative held-out IC."
            if best_ic < 0 and allow_negative_ic
            else "Accepted using held-out walk-forward validation."
        ),
    }
    with (artifact_path / "evaluation_report.json").open("w", encoding="utf-8") as f:
        json.dump(evaluation_report, f, indent=2)

    return metrics_json
