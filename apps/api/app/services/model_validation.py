from __future__ import annotations

from functools import lru_cache
from math import sqrt
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings
from app.ml.lightgbm_alpha.artifact_loader import try_load_lightgbm_artifact
from app.ml.lightgbm_alpha.runtime import import_lightgbm
from app.services.model_runtime import api_root


def _spearman_rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return 0.0
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
        f"Not enough decision dates to compute walk-forward validation (found={decision_dates_count}, need at least {sum(bootstrap)})."
    )


def _resolve_dataset_path(artifact_dir_name: str) -> Path:
    return api_root() / "artifacts" / "datasets" / artifact_dir_name / "ml_dataset.csv"


@lru_cache(maxsize=4)
def _cached_validation_overview(cache_key: str, dataset_path_str: str) -> dict[str, Any]:
    del cache_key

    artifact = try_load_lightgbm_artifact()
    if artifact is None:
        return {"available": False, "notes": ["LightGBM artifact is missing."]}

    dataset_path = Path(dataset_path_str)
    if not dataset_path.exists():
        return {"available": False, "notes": [f"Validation dataset is missing at {dataset_path}."]}

    lgb, _runtime_site_packages = import_lightgbm()
    if lgb is None:
        return {"available": False, "notes": ["LightGBM could not be imported for walk-forward validation."]}

    df = pd.read_csv(dataset_path)
    if df.empty:
        return {"available": False, "notes": ["Validation dataset is empty."]}

    df["decision_date"] = pd.to_datetime(df["decision_date"]).dt.date
    feature_order: list[str] = list(artifact.feature_manifest.get("feature_order", []))
    if not feature_order:
        return {"available": False, "notes": ["Feature manifest is missing feature_order."]}

    decision_dates = sorted(df["decision_date"].unique())
    initial_train_dates, val_dates_count, test_dates_count, embargo_dates = _resolve_walk_forward_windows(len(decision_dates))
    model_hyperparams = dict(artifact.feature_manifest.get("model_hyperparams", {}))
    prediction_horizon_days = int(artifact.feature_manifest.get("prediction_horizon_days", 21))
    date_to_idx = {d: df.index[df["decision_date"] == d].to_numpy() for d in decision_dates}

    trade_rows: list[dict[str, Any]] = []
    total_matches = 0
    total_predictions = 0
    fold_count = 0
    train_end = initial_train_dates

    while True:
        if train_end + embargo_dates + val_dates_count + test_dates_count > len(decision_dates):
            break

        train_dates = decision_dates[:train_end]
        val_dates = decision_dates[train_end + embargo_dates : train_end + embargo_dates + val_dates_count]
        test_dates = decision_dates[
            train_end + embargo_dates + val_dates_count : train_end + embargo_dates + val_dates_count + test_dates_count
        ]

        train_idx = np.concatenate([date_to_idx[d] for d in train_dates]) if train_dates else np.array([], dtype=int)
        val_idx = np.concatenate([date_to_idx[d] for d in val_dates]) if val_dates else np.array([], dtype=int)
        if len(train_idx) == 0 or len(val_idx) == 0 or not test_dates:
            train_end += val_dates_count
            continue

        X_train = df.loc[df.index[train_idx], feature_order]
        y_train = df.loc[df.index[train_idx], "target_21d"]
        X_val = df.loc[df.index[val_idx], feature_order]
        y_val = df.loc[df.index[val_idx], "target_21d"]

        model = lgb.LGBMRegressor(**model_hyperparams, random_state=42)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)],
        )

        for test_date in test_dates:
            subset = df.loc[df.index[date_to_idx[test_date]]].copy()
            if subset.empty:
                continue
            y_true = subset["target_21d"].to_numpy(dtype=float)
            y_pred = model.predict(subset[feature_order])
            hit_matches = int(np.sum(np.sign(y_true) == np.sign(y_pred)))
            sample_count = int(len(subset))
            total_matches += hit_matches
            total_predictions += sample_count
            trade_rows.append(
                {
                    "date": test_date.isoformat(),
                    "period_return": _top_bottom_spread(y_true, y_pred),
                    "information_coefficient": _spearman_rank_ic(y_true, y_pred),
                    "hit_rate": (hit_matches / sample_count) if sample_count else 0.0,
                    "sample_count": sample_count,
                }
            )

        fold_count += 1
        train_end += val_dates_count

    if not trade_rows:
        return {"available": False, "notes": ["Walk-forward validation could not produce any out-of-sample rows."]}

    trade_rows.sort(key=lambda row: row["date"])
    equity_index = 100.0
    equity_curve: list[dict[str, Any]] = []
    for row in trade_rows:
        equity_index *= 1.0 + float(row["period_return"])
        equity_curve.append(
            {
                "date": row["date"],
                "equity_index": round(equity_index, 2),
                "period_return_pct": round(float(row["period_return"]) * 100.0, 2),
                "information_coefficient": round(float(row["information_coefficient"]), 4),
                "hit_rate_pct": round(float(row["hit_rate"]) * 100.0, 2),
                "sample_count": row["sample_count"],
            }
        )

    returns = np.array([float(row["period_return"]) for row in trade_rows], dtype=float)
    avg_return = float(np.mean(returns)) if len(returns) else 0.0
    std_return = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    period_risk_free = 0.07 * (prediction_horizon_days / 252.0)
    sharpe_ratio = (
        ((avg_return - period_risk_free) / max(std_return, 1e-9)) * sqrt(252.0 / prediction_horizon_days)
        if std_return > 0
        else 0.0
    )

    notes: list[str] = []
    selection_status = str(artifact.metrics.get("selection_status") or "unknown")
    if "negative_ic" in selection_status:
        notes.append("Current LightGBM artifact was accepted in bootstrap mode despite negative held-out IC.")

    return {
        "available": True,
        "model_version": artifact.feature_manifest.get("model_version", artifact.artifact_dir.name),
        "training_mode": artifact.metadata.get("training_mode", artifact.metrics.get("training_mode", "unknown")),
        "prediction_horizon_days": prediction_horizon_days,
        "selection_status": selection_status,
        "fold_count": fold_count,
        "sample_count": total_predictions,
        "oos_sharpe_ratio": round(float(sharpe_ratio), 3),
        "information_coefficient": round(float(np.mean([row["information_coefficient"] for row in trade_rows])), 4),
        "hit_rate_pct": round((total_matches / total_predictions) * 100.0, 2) if total_predictions else 0.0,
        "avg_top_bottom_spread_pct": round(float(np.mean(returns)) * 100.0, 2),
        "walk_forward_equity_curve": equity_curve,
        "notes": notes,
    }


def get_lightgbm_validation_overview() -> dict[str, Any]:
    artifact = try_load_lightgbm_artifact()
    if artifact is None:
        return {"available": False, "notes": ["LightGBM artifact is missing."]}

    dataset_path = _resolve_dataset_path(Path(settings.ml_lightgbm_artifact_dir).name)
    model_mtime = artifact.model_file_path.stat().st_mtime if artifact.model_file_path.exists() else 0
    dataset_mtime = dataset_path.stat().st_mtime if dataset_path.exists() else 0
    cache_key = f"{artifact.feature_manifest.get('model_version', artifact.artifact_dir.name)}:{model_mtime}:{dataset_mtime}"
    return _cached_validation_overview(cache_key, str(dataset_path))
