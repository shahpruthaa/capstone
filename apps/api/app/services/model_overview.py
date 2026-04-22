from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.services.db_quant_engine import get_effective_trade_date, load_snapshots, predict_ensemble_for_snapshots
from app.services.model_runtime import get_model_runtime_status
from app.services.model_validation import get_lightgbm_validation_overview


def _compute_health_score(runtime_status: dict[str, Any], validation_overview: dict[str, Any]) -> int:
    if not runtime_status.get("available"):
        return 35

    score = 90
    if runtime_status.get("active_mode") == "degraded_ensemble":
        score -= 12
    if runtime_status.get("artifact_classification") == "bootstrap":
        score -= 10

    ic = validation_overview.get("information_coefficient")
    if isinstance(ic, (int, float)):
        if ic < 0:
            score -= 20
        elif ic < 0.05:
            score -= 8

    hit_rate = validation_overview.get("hit_rate_pct")
    if isinstance(hit_rate, (int, float)) and hit_rate < 50:
        score -= 8

    return max(0, min(100, int(round(score))))


def _build_current_signals(db: Session, limit: int = 6) -> dict[str, Any]:
    as_of_date = get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=126)
    if not snapshots:
        return {"as_of_date": as_of_date.isoformat(), "signals": [], "notes": ["No snapshots are available for signal preview."]}

    predictions_by_symbol, model_info = predict_ensemble_for_snapshots(db, snapshots, as_of_date)
    if not predictions_by_symbol:
        return {
            "as_of_date": as_of_date.isoformat(),
            "signals": [],
            "notes": [f"No usable ensemble signals are available: {model_info.get('reason', 'unknown')}."],
        }

    snapshot_map = {snapshot.symbol: snapshot for snapshot in snapshots if snapshot.instrument_type == "EQUITY"}
    raw_scores = np.array([float(pred.pred_21d_return) for pred in predictions_by_symbol.values()], dtype=float)
    score_mean = float(np.mean(raw_scores)) if len(raw_scores) else 0.0
    score_std = float(np.std(raw_scores, ddof=1)) if len(raw_scores) > 1 else 0.0
    scored = []

    for symbol, pred in predictions_by_symbol.items():
        snapshot = snapshot_map.get(symbol)
        if snapshot is None:
            continue
        raw_score = float(pred.pred_21d_return)
        normalized = abs((raw_score - score_mean) / score_std) if score_std > 1e-9 else abs(raw_score)
        confidence = max(0.0, min(1.0, normalized / 3.0))
        action = "BUY" if raw_score > 0.015 else "SELL" if raw_score < -0.015 else "HOLD"
        scored.append(
            {
                "symbol": symbol,
                "sector": snapshot.sector,
                "action": action,
                "confidence": round(confidence, 3),
                "predicted_return_21d_pct": round(raw_score * 100.0, 2),
                "predicted_annual_return_pct": round(float(pred.pred_annual_return) * 100.0, 2),
                "top_drivers": list(pred.top_drivers[:3]),
            }
        )

    scored.sort(key=lambda row: (abs(float(row["predicted_return_21d_pct"])), float(row["confidence"])), reverse=True)
    return {
        "as_of_date": as_of_date.isoformat(),
        "signals": scored[:limit],
        "notes": [],
    }


def build_current_model_overview(db: Session) -> dict[str, Any]:
    runtime_status = get_model_runtime_status()
    validation_overview = get_lightgbm_validation_overview()
    current_signals = _build_current_signals(db)

    overview = dict(runtime_status)
    overview["validation_overview"] = validation_overview
    overview["current_signals"] = current_signals["signals"]
    overview["current_signals_as_of_date"] = current_signals["as_of_date"]
    overview["health_score_pct"] = _compute_health_score(runtime_status, validation_overview)

    notes = list(runtime_status.get("notes", []))
    notes.extend(validation_overview.get("notes", []))
    notes.extend(current_signals.get("notes", []))
    overview["notes"] = notes
    return overview
