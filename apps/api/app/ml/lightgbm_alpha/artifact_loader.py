from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.ml.lightgbm_alpha.runtime import import_lightgbm


LIGHTGBM_ARTIFACT_DIR = settings.ml_lightgbm_artifact_dir
FEATURE_MANIFEST_FILE = "feature_manifest.json"
METRICS_FILE = "metrics.json"
METADATA_FILE = "metadata.json"
MODEL_FILE = "model.txt"
EVALUATION_REPORT_FILE = "evaluation_report.json"


@dataclass(frozen=True)
class LightGBMArtifact:
    artifact_dir: Path
    feature_manifest: dict[str, Any]
    metrics: dict[str, Any]
    metadata: dict[str, Any]
    model_file_path: Path
    evaluation_report: dict[str, Any]


def _api_root() -> Path:
    # .../apps/api/app/ml/lightgbm_alpha/artifact_loader.py -> .../apps/api
    return Path(__file__).resolve().parents[2]


def _resolve_artifact_dir() -> Path:
    relative = Path(LIGHTGBM_ARTIFACT_DIR)
    if relative.is_absolute():
        return relative

    preferred = _api_root() / relative
    legacy = _api_root().parent / relative
    for candidate in (preferred, legacy):
        if candidate.exists():
            return candidate

    for configured in (preferred, legacy):
        versioned = _latest_versioned_artifact_dir(configured)
        if versioned is not None:
            return versioned
    return preferred


def _latest_versioned_artifact_dir(configured_path: Path) -> Path | None:
    parent = configured_path.parent
    stem = configured_path.name.rsplit("_v", 1)[0]
    if not parent.exists() or not stem:
        return None
    matches = sorted(
        (path for path in parent.glob(f"{stem}_v*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    return matches[0] if matches else None


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def try_load_lightgbm_artifact() -> LightGBMArtifact | None:
    artifact_dir = _resolve_artifact_dir()
    manifest_path = artifact_dir / FEATURE_MANIFEST_FILE
    metrics_path = artifact_dir / METRICS_FILE
    metadata_path = artifact_dir / METADATA_FILE
    model_path = artifact_dir / MODEL_FILE
    evaluation_report_path = artifact_dir / EVALUATION_REPORT_FILE

    if not manifest_path.exists() or not model_path.exists():
        return None

    try:
        feature_manifest = _read_json(manifest_path)
        metrics = _read_json(metrics_path) if metrics_path.exists() else {}
        metadata = _read_json(metadata_path) if metadata_path.exists() else {}
        evaluation_report = _read_json(evaluation_report_path) if evaluation_report_path.exists() else {}
    except Exception:
        return None

    required_manifest_keys = {
        "model_version",
        "prediction_horizon_days",
        "feature_order",
        "numeric_features",
        "categorical_features",
        "sector_mapping",
        "market_cap_bucket_mapping",
        "model_hyperparams",
    }
    if not required_manifest_keys.issubset(set(feature_manifest.keys())):
        return None

    return LightGBMArtifact(
        artifact_dir=artifact_dir,
        feature_manifest=feature_manifest,
        metrics=metrics,
        metadata=metadata,
        model_file_path=model_path,
        evaluation_report=evaluation_report,
    )


def get_lightgbm_model_status() -> dict[str, Any]:
    artifact = try_load_lightgbm_artifact()
    if artifact is None:
        return {"available": False, "variant": "LIGHTGBM_HYBRID", "reason": "artifact_missing"}

    _lgb, runtime_site_packages = import_lightgbm()
    if _lgb is None:
        return {"available": False, "variant": "LIGHTGBM_HYBRID", "reason": "lightgbm_import_failed"}

    # Avoid loading Booster at startup (slow); manifest + file presence are enough for status.
    try:
        if not artifact.model_file_path.is_file() or artifact.model_file_path.stat().st_size == 0:
            return {"available": False, "variant": "LIGHTGBM_HYBRID", "reason": "model_load_failed"}
    except OSError:
        return {"available": False, "variant": "LIGHTGBM_HYBRID", "reason": "model_load_failed"}

    training_mode = str(artifact.metadata.get("training_mode") or artifact.metrics.get("training_mode") or "unknown")
    best_ic = artifact.metrics.get("best_avg_spearman_ic")
    top_bottom_spread = artifact.metrics.get("avg_top_bottom_spread")
    if top_bottom_spread is None:
        spreads = [
            float(fold["avg_top_bottom_spread"])
            for fold in artifact.metrics.get("folds", [])
            if isinstance(fold, dict) and fold.get("avg_top_bottom_spread") is not None
        ]
        top_bottom_spread = (sum(spreads) / len(spreads)) if spreads else None
    validation_summary = {
        "best_avg_spearman_ic": best_ic,
        "avg_top_bottom_spread": top_bottom_spread,
        "selection_status": artifact.metrics.get("selection_status"),
    }

    return {
        "available": True,
        "variant": "LIGHTGBM_HYBRID",
        "model_version": artifact.feature_manifest.get("model_version", "unknown"),
        "prediction_horizon_days": artifact.feature_manifest.get("prediction_horizon_days", 21),
        "training_mode": training_mode,
        "artifact_classification": "bootstrap" if training_mode == "bootstrap" else "standard",
        "training_metadata": artifact.metadata,
        "validation_metrics": artifact.metrics,
        "validation_summary": validation_summary,
        "evaluation_report": artifact.evaluation_report,
        "runtime_site_packages": runtime_site_packages,
    }
