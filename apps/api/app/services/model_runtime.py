from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.ml.lightgbm_alpha.artifact_loader import try_load_lightgbm_artifact
from app.ml.lightgbm_alpha.runtime import import_lightgbm


def api_root() -> Path:
    # .../apps/api/app/services/model_runtime.py -> .../apps/api
    return Path(__file__).resolve().parents[2]


def resolve_artifact_dir(relative_or_absolute: str) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path

    # Prefer artifacts rooted at apps/api, with fallback to legacy apps/ root.
    preferred = api_root() / path
    legacy = api_root().parent / path
    candidates = [preferred, legacy]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    versioned = _latest_versioned_artifact_dir(preferred)
    if versioned is not None:
        return versioned
    legacy_versioned = _latest_versioned_artifact_dir(legacy)
    if legacy_versioned is not None:
        return legacy_versioned
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


def _safe_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _component_payload(
    *,
    name: str,
    artifact_dir: Path,
    available: bool,
    reason: str | None = None,
    version: str | None = None,
    artifact_classification: str = "missing",
    training_mode: str | None = None,
    prediction_horizon_days: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "available": available,
        "artifact_dir": str(artifact_dir),
        "reason": reason,
        "version": version or "unknown",
        "artifact_classification": artifact_classification,
        "training_mode": training_mode or "unknown",
        "prediction_horizon_days": prediction_horizon_days,
        "metadata": metadata or {},
    }


def load_ensemble_manifest() -> dict[str, Any]:
    artifact_dir = resolve_artifact_dir(settings.ml_ensemble_artifact_dir)
    manifest_path = artifact_dir / "ensemble_manifest.json"
    if manifest_path.exists():
        manifest = _safe_json(manifest_path)
        if manifest:
            manifest.setdefault("model_version", artifact_dir.name)
            manifest.setdefault("artifact_classification", "standard")
            manifest.setdefault("prediction_horizon_days", 21)
            manifest.setdefault("component_weights", {"lightgbm": 0.50, "lstm": 0.25, "gnn": 0.15})
            manifest.setdefault("death_risk_penalty", 1.5)
            return manifest
    return {
        "model_version": "ensemble_v1_default",
        "artifact_classification": "bootstrap",
        "prediction_horizon_days": 21,
        "component_weights": {"lightgbm": 0.50, "lstm": 0.25, "gnn": 0.15},
        "death_risk_penalty": 1.5,
        "reason": "ensemble_manifest_missing",
    }


def get_lightgbm_component_status() -> dict[str, Any]:
    artifact_dir = resolve_artifact_dir(settings.ml_lightgbm_artifact_dir)
    artifact = try_load_lightgbm_artifact()
    if artifact is None:
        return _component_payload(name="lightgbm", artifact_dir=artifact_dir, available=False, reason="artifact_missing")
    lgb, runtime_site_packages = import_lightgbm()
    if lgb is None:
        return _component_payload(name="lightgbm", artifact_dir=artifact_dir, available=False, reason="lightgbm_import_failed")
    try:
        lgb.Booster(model_file=str(artifact.model_file_path))
    except Exception:
        return _component_payload(name="lightgbm", artifact_dir=artifact_dir, available=False, reason="model_load_failed")
    training_mode = str(artifact.metadata.get("training_mode") or artifact.metrics.get("training_mode") or "unknown")
    return _component_payload(
        name="lightgbm",
        artifact_dir=artifact_dir,
        available=True,
        version=str(artifact.feature_manifest.get("model_version", artifact_dir.name)),
        artifact_classification="bootstrap" if training_mode == "bootstrap" else "standard",
        training_mode=training_mode,
        prediction_horizon_days=int(artifact.feature_manifest.get("prediction_horizon_days", 21)),
        metadata={
            "validation_metrics": artifact.metrics,
            "evaluation_report": artifact.evaluation_report,
            "training_metadata": artifact.metadata,
            "runtime_site_packages": runtime_site_packages,
        },
    )


def get_lstm_component_status() -> dict[str, Any]:
    artifact_dir = resolve_artifact_dir(settings.ml_lstm_artifact_dir)
    model_path = artifact_dir / "lstm_model.pt"
    config_path = artifact_dir / "lstm_config.json"
    metrics_path = artifact_dir / "lstm_metrics.json"
    metadata_path = artifact_dir / "lstm_metadata.json"
    norm_path = artifact_dir / "norm_stats.json"
    if not model_path.exists() or not config_path.exists():
        return _component_payload(name="lstm", artifact_dir=artifact_dir, available=False, reason="artifact_missing")
    try:
        import torch

        torch.load(model_path, map_location="cpu")
    except Exception:
        return _component_payload(name="lstm", artifact_dir=artifact_dir, available=False, reason="model_load_failed")
    metadata = _safe_json(metadata_path)
    metrics = _safe_json(metrics_path)
    config = _safe_json(config_path)
    training_mode = str(metadata.get("training_mode") or config.get("training_mode") or "unknown")
    return _component_payload(
        name="lstm",
        artifact_dir=artifact_dir,
        available=True,
        version=str(metadata.get("model_version") or artifact_dir.name),
        artifact_classification="bootstrap" if training_mode == "bootstrap" else "standard",
        training_mode=training_mode,
        prediction_horizon_days=int(metadata.get("prediction_horizon_days", 21)),
        metadata={"metrics": metrics, "metadata": metadata, "norm_stats_present": norm_path.exists()},
    )


def get_gnn_component_status() -> dict[str, Any]:
    artifact_dir = resolve_artifact_dir(settings.ml_gnn_artifact_dir)
    model_path = artifact_dir / "gnn_model.pt"
    embeddings_path = artifact_dir / "gnn_embeddings.json"
    metadata_path = artifact_dir / "gnn_metadata.json"
    if not model_path.exists() or not embeddings_path.exists():
        return _component_payload(name="gnn", artifact_dir=artifact_dir, available=False, reason="artifact_missing")
    metadata = _safe_json(metadata_path)
    try:
        with embeddings_path.open("r", encoding="utf-8") as handle:
            embeddings = json.load(handle)
    except Exception:
        return _component_payload(name="gnn", artifact_dir=artifact_dir, available=False, reason="embedding_load_failed")
    training_mode = str(metadata.get("training_mode", "unknown"))
    return _component_payload(
        name="gnn",
        artifact_dir=artifact_dir,
        available=True,
        version=str(metadata.get("model_version") or artifact_dir.name),
        artifact_classification="bootstrap" if training_mode == "bootstrap" else "standard",
        training_mode=training_mode,
        prediction_horizon_days=int(metadata.get("prediction_horizon_days", 21)),
        metadata={"embedding_count": len(embeddings), "metadata": metadata},
    )


def get_death_risk_component_status() -> dict[str, Any]:
    artifact_dir = resolve_artifact_dir(settings.ml_death_risk_artifact_dir)
    model_path = artifact_dir / "death_risk_model.pkl"
    scaler_path = artifact_dir / "death_risk_scaler.pkl"
    metrics_path = artifact_dir / "death_risk_metrics.json"
    metadata_path = artifact_dir / "death_risk_metadata.json"
    if not model_path.exists() or not scaler_path.exists():
        return _component_payload(name="death_risk", artifact_dir=artifact_dir, available=False, reason="artifact_missing")
    try:
        with model_path.open("rb") as handle:
            pickle.load(handle)
        with scaler_path.open("rb") as handle:
            pickle.load(handle)
    except Exception:
        return _component_payload(name="death_risk", artifact_dir=artifact_dir, available=False, reason="artifact_load_failed")
    metadata = _safe_json(metadata_path)
    metrics = _safe_json(metrics_path)
    training_mode = str(metadata.get("training_mode", "unknown"))
    return _component_payload(
        name="death_risk",
        artifact_dir=artifact_dir,
        available=True,
        version=str(metadata.get("model_version") or artifact_dir.name),
        artifact_classification="bootstrap" if training_mode == "bootstrap" else "standard",
        training_mode=training_mode,
        prediction_horizon_days=int(metadata.get("prediction_horizon_days", 21)),
        metadata={"metrics": metrics, "metadata": metadata},
    )


def get_groq_component_status() -> dict[str, Any]:
    configured = bool(settings.groq_api_key)
    return {
        "name": "groq",
        "available": configured,
        "configured": configured,
        "reason": None if configured else "api_key_missing",
        "model": settings.groq_model,
    }


def get_component_statuses() -> dict[str, dict[str, Any]]:
    return {
        "lightgbm": get_lightgbm_component_status(),
        "lstm": get_lstm_component_status(),
        "gnn": get_gnn_component_status(),
        "death_risk": get_death_risk_component_status(),
        "groq": get_groq_component_status(),
    }


def get_model_runtime_status() -> dict[str, Any]:
    components = get_component_statuses()
    lightgbm = components["lightgbm"]
    ensemble_manifest = load_ensemble_manifest()
    available_ml_components = [name for name in ("lightgbm", "lstm", "gnn", "death_risk") if components[name]["available"]]
    missing_ml_components = [name for name in ("lightgbm", "lstm", "gnn", "death_risk") if not components[name]["available"]]

    if lightgbm["available"] and components["lstm"]["available"] and components["gnn"]["available"] and components["death_risk"]["available"]:
        active_mode = "full_ensemble"
        available = True
        reason = None
    elif lightgbm["available"]:
        active_mode = "degraded_ensemble"
        available = True
        reason = "non_core_components_missing"
    else:
        active_mode = "rules_only"
        available = False
        reason = lightgbm.get("reason") or "ensemble_core_missing"

    manifest_present = ensemble_manifest.get("reason") != "ensemble_manifest_missing"
    artifact_classification = str(
        (ensemble_manifest.get("artifact_classification") if manifest_present else None)
        or lightgbm.get("artifact_classification")
        or ("missing" if not available else "standard")
    )
    training_mode = str(
        ensemble_manifest.get("training_mode")
        or lightgbm.get("training_mode")
        or "unknown"
    )
    notes = []
    if available:
        if active_mode == "full_ensemble":
            notes.append("Full ensemble runtime is available: LightGBM, LSTM, GNN, and death-risk components are ready.")
        else:
            notes.append(
                f"Degraded ensemble runtime is active. Available: {', '.join(available_ml_components)}. Missing: {', '.join(missing_ml_components)}."
            )
    else:
        notes.append("Rules-only fallback is active because the LightGBM artifact is missing or could not be loaded.")
    if not components["groq"]["available"]:
        notes.append("Groq is not configured, so explanation and market-context endpoints will degrade gracefully.")

    return {
        "available": available,
        "variant": "LIGHTGBM_HYBRID" if available else "RULES",
        "model_source": "ENSEMBLE" if available else "RULES",
        "active_mode": active_mode,
        "model_version": str(ensemble_manifest.get("model_version") or lightgbm.get("version") or "rules"),
        "prediction_horizon_days": int(ensemble_manifest.get("prediction_horizon_days") or lightgbm.get("prediction_horizon_days") or 21),
        "training_mode": training_mode,
        "artifact_classification": artifact_classification,
        "available_components": available_ml_components,
        "missing_components": missing_ml_components,
        "components": components,
        "groq_connected": bool(components["groq"]["available"]),
        "groq_model": settings.groq_model,
        "ensemble_manifest": ensemble_manifest,
        "reason": reason,
        "notes": notes,
        "validation_metrics": lightgbm.get("metadata", {}).get("validation_metrics", {}),
        "validation_summary": lightgbm.get("metadata", {}).get("validation_metrics", {}),
        "training_metadata": lightgbm.get("metadata", {}).get("training_metadata", {}),
        "evaluation_report": lightgbm.get("metadata", {}).get("evaluation_report", {}),
        "runtime_site_packages": lightgbm.get("metadata", {}).get("runtime_site_packages"),
    }
