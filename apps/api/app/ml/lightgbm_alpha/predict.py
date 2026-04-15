from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ml.lightgbm_alpha.artifact_loader import try_load_lightgbm_artifact
from app.ml.lightgbm_alpha.features import compute_snapshot_features
from app.ml.lightgbm_alpha.runtime import import_lightgbm


@dataclass(frozen=True)
class MLPrediction:
    pred_21d_return: float
    pred_annual_return: float
    top_drivers: list[str]
    component_scores: dict[str, float] = field(default_factory=dict)


def _calibrate_pred_21d_to_annual(pred_21d: float, horizon_days: int = 21) -> float:
    # Annualize with the same engineering rule used in the design doc.
    pred_annual = (1.0 + pred_21d) ** (252 / horizon_days) - 1.0
    return float(min(0.40, max(-0.20, pred_annual)))


def _winsorize_and_zscore(feature_rows: list[dict[str, float]], numeric_features: list[str]) -> list[dict[str, float]]:
    """
    Winsorize numeric features at 1st/99th and z-score across the inference cross-section.
    """
    import numpy as np

    out: list[dict[str, float]] = []
    for f in numeric_features:
        values = [row.get(f) for row in feature_rows]
        values = [v for v in values if v is not None]
        if not values:
            continue
        p1 = float(np.quantile(values, 0.01))
        p99 = float(np.quantile(values, 0.99))
        clipped = [min(p99, max(p1, float(row.get(f, 0.0)))) for row in feature_rows]
        mean = float(np.mean(clipped))
        std = float(np.std(clipped, ddof=1)) if len(clipped) > 1 else 0.0
        if std <= 1e-12:
            std = 1.0
        for i, row in enumerate(feature_rows):
            row[f] = (clipped[i] - mean) / std

    # Return the mutated rows (the caller treats them as transformed).
    for row in feature_rows:
        out.append({k: float(v) for k, v in row.items() if v is not None})
    return out


class LightGBMAlphaPredictor:
    def __init__(self) -> None:
        self._artifact = try_load_lightgbm_artifact()
        self._booster = None

    @property
    def available(self) -> bool:
        return self._artifact is not None

    def _ensure_model_loaded(self) -> None:
        if self._artifact is None:
            return
        if self._booster is not None:
            return
        lgb, _ = import_lightgbm()
        if lgb is None:
            self._booster = None
            return

        try:
            self._booster = lgb.Booster(model_file=str(self._artifact.model_file_path))
        except Exception:
            self._booster = None

    def predict(self, snapshots: list[Any]) -> tuple[dict[str, MLPrediction], dict[str, Any]]:
        """
        Returns:
          predictions_by_symbol: only for snapshots with valid features & model loaded.
          model_info: dict for response notes.
        """
        if not self.available:
            return {}, {"available": False, "reason": "artifact_missing"}

        self._ensure_model_loaded()
        if self._booster is None:
            return {}, {"available": False, "reason": "model_unavailable_or_import_error"}

        feature_manifest = self._artifact.feature_manifest
        feature_order: list[str] = feature_manifest["feature_order"]
        numeric_features: list[str] = feature_manifest["numeric_features"]
        categorical_features: list[str] = feature_manifest["categorical_features"]
        sector_mapping: dict[str, int] = feature_manifest["sector_mapping"]
        market_cap_bucket_mapping: dict[str, int] = feature_manifest["market_cap_bucket_mapping"]

        sector_unknown = sector_mapping.get("Unknown", sector_mapping.get("__UNK__", 0))
        cap_bucket_unknown = market_cap_bucket_mapping.get("Unknown", market_cap_bucket_mapping.get("__UNK__", 0))

        raw_rows: list[dict[str, float]] = []
        valid_symbols: list[str] = []
        invalid_symbols: list[str] = []

        snapshot_rows: list[tuple[str, dict[str, float]]] = []
        for snapshot in snapshots:
            symbol = getattr(snapshot, "symbol", None)
            if not symbol:
                continue
            base = compute_snapshot_features(snapshot)
            # Add categoricals.
            sector = getattr(snapshot, "sector", None) or "Unknown"
            cap_bucket = getattr(snapshot, "market_cap_bucket", None) or "Unknown"
            base["sector_cat"] = float(sector_mapping.get(str(sector), sector_unknown))
            base["market_cap_bucket_cat"] = float(market_cap_bucket_mapping.get(str(cap_bucket), cap_bucket_unknown))
            snapshot_rows.append((str(symbol), base))

        if not snapshot_rows:
            return {}, {"available": False, "reason": "no_valid_rows"}

        # Liquidity percentile: computed across the inference cross-section.
        if "liquidity_percentile" in numeric_features:
            tov_by_sym = []
            for sym, row in snapshot_rows:
                tov = row.get("avg_traded_value_20d")
                if tov is not None:
                    tov_by_sym.append((sym, float(tov)))
            tov_by_sym_sorted = sorted(tov_by_sym, key=lambda x: x[1])
            sym_to_rank = {sym: rank for rank, (sym, _) in enumerate(tov_by_sym_sorted)}
            n = max(1, len(tov_by_sym_sorted))
            for sym, row in snapshot_rows:
                if sym in sym_to_rank:
                    # Percentile in [0,1].
                    row["liquidity_percentile"] = float(sym_to_rank[sym] / max(n - 1, 1))

        # Validate required numeric features exist for prediction.
        for sym, row in snapshot_rows:
            missing_numeric = [f for f in numeric_features if f not in row]
            if missing_numeric:
                invalid_symbols.append(sym)
                continue
            raw_rows.append(row)
            valid_symbols.append(sym)

        if not raw_rows:
            return {}, {"available": False, "reason": "no_valid_rows_after_feature_checks"}

        # Transform (in-place) then reassemble X.
        transformed_rows = _winsorize_and_zscore(raw_rows, numeric_features)
        # Build X for rows in the same order as transformed_rows.
        import numpy as np

        X = np.zeros((len(transformed_rows), len(feature_order)), dtype=float)
        for i, row in enumerate(transformed_rows):
            for j, fname in enumerate(feature_order):
                X[i, j] = float(row.get(fname, 0.0))

        # Predict.
        pred = self._booster.predict(X)
        # Contributions for drivers.
        try:
            contrib = self._booster.predict(X, pred_contrib=True)
        except Exception:
            contrib = None

        predictions_by_symbol: dict[str, MLPrediction] = {}
        horizon_days = int(feature_manifest.get("prediction_horizon_days", 21))

        # Map predictions back.
        for i, symbol in enumerate(valid_symbols):
            pred_21d = float(pred[i])
            pred_annual = _calibrate_pred_21d_to_annual(pred_21d, horizon_days=horizon_days)

            top_drivers: list[str] = []
            if contrib is not None:
                row_contrib = contrib[i]
                # LightGBM returns contributions: [f1, f2, ..., fN, bias]
                per_feature = row_contrib[:-1] if len(row_contrib) == len(feature_order) + 1 else row_contrib
                # Pick top 3 absolute contributions.
                pairs = [(feature_order[k], float(per_feature[k])) for k in range(min(len(feature_order), len(per_feature)))]
                pairs.sort(key=lambda x: abs(x[1]), reverse=True)
                top_drivers = [f"{name}:{val:+.3f}" for name, val in pairs[:3]]

            predictions_by_symbol[symbol] = MLPrediction(
                pred_21d_return=pred_21d,
                pred_annual_return=pred_annual,
                top_drivers=top_drivers,
                component_scores={"lightgbm_raw_21d": pred_21d, "lightgbm_annual": pred_annual},
            )

        model_info = {
            "available": True,
            "model_version": self._artifact.feature_manifest.get("model_version", "unknown"),
            "prediction_horizon_days": horizon_days,
            "invalid_rows": invalid_symbols,
            "used_rows": valid_symbols,
        }
        return predictions_by_symbol, model_info
