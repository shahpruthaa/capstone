from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.lightgbm_alpha.predict import LightGBMAlphaPredictor, MLPrediction
from app.services.model_runtime import get_component_statuses, load_ensemble_manifest, resolve_artifact_dir

logger = logging.getLogger(__name__)

class EnsembleScorer:
    def __init__(self):
        self.lgb_predictor = LightGBMAlphaPredictor()
        self.component_status = get_component_statuses()
        self.ensemble_manifest = load_ensemble_manifest()
        self._gnn_embeddings = {}
        self._lstm_model = None
        self._lstm_norm_stats = {}
        self._load_gnn()
        self._load_lstm()

    def _load_gnn(self):
        try:
            path = resolve_artifact_dir(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
            if path.exists():
                with open(path) as f:
                    self._gnn_embeddings = json.load(f)
                logger.info(f"GNN embeddings loaded: {len(self._gnn_embeddings)} symbols")
        except Exception as e:
            logger.warning(f"GNN load failed: {e}")

    def _load_lstm(self):
        try:
            import torch
            from app.ml.lstm_alpha.train import LSTMForecaster
            base = resolve_artifact_dir(settings.ml_lstm_artifact_dir)
            config_path = base / "lstm_config.json"
            model_path = base / "lstm_model.pt"
            norm_path = base / "norm_stats.json"
            if not model_path.exists():
                logger.warning("LSTM model not found, skipping")
                return
            with open(config_path) as f:
                cfg = json.load(f)
            model = LSTMForecaster(
                input_size=cfg.get("input_dim", 4),
                hidden_size=cfg.get("hidden_dim", 64),
                num_layers=cfg.get("num_layers", 2),
            )
            model.load_state_dict(torch.load(str(model_path), map_location="cpu"))
            model.eval()
            self._lstm_model = model
            if norm_path.exists():
                with open(norm_path) as f:
                    self._lstm_norm_stats = json.load(f)
            logger.info("LSTM model loaded into ensemble")
        except Exception as e:
            logger.warning(f"LSTM load failed: {e}")

    def _get_lstm_scores(self, snapshots) -> dict[str, float]:
        if self._lstm_model is None:
            return {}
        try:
            import torch
            scores = {}
            for s in snapshots:
                closes = [float(v) for _, v in (s.adjusted_closes or [])]
                if len(closes) < 20:
                    continue
                c = closes[-20:]
                # Normalize using training stats if available
                def norm(vals, key):
                    stats = self._lstm_norm_stats.get(key)
                    if stats:
                        mean, std = stats[0], stats[1]
                        std = std if std > 1e-8 else 1.0
                        return [(v - mean) / std for v in vals]
                    mean = sum(vals) / len(vals)
                    std = (sum((v-mean)**2 for v in vals)/len(vals))**0.5 or 1.0
                    return [(v - mean) / std for v in vals]

                returns = [(c[i]/c[i-1] - 1) if c[i-1] != 0 else 0.0 for i in range(1, 20)]
                returns = [0.0] + returns

                highs = [float(v) for _, v in (s.adjusted_highs or [])][-20:] if s.adjusted_highs else c
                lows = [float(v) for _, v in (s.adjusted_lows or [])][-20:] if s.adjusted_lows else c
                hlr = [(highs[i]/(lows[i]+1e-8)) if lows[i] != 0 else 1.0 for i in range(min(len(highs), len(lows), 20))]
                while len(hlr) < 20:
                    hlr.append(1.0)

                cn = norm(c, "close_0")
                rn = norm(returns, "return_0")
                hn = norm(hlr, "high_low_ratio_0")
                vols = [0.0] * 20  # volume proxy

                seq = torch.zeros(1, 20, 4, dtype=torch.float32)
                for i in range(20):
                    seq[0, i, 0] = cn[i] if i < len(cn) else 0.0
                    seq[0, i, 1] = vols[i]
                    seq[0, i, 2] = rn[i] if i < len(rn) else 0.0
                    seq[0, i, 3] = hn[i] if i < len(hn) else 1.0

                with torch.no_grad():
                    pred = self._lstm_model(seq).item()
                scores[s.symbol] = float(pred)
            return scores
        except Exception as e:
            logger.warning(f"LSTM inference failed: {e}")
            return {}

    @staticmethod
    def _zscore(scores):
        if not scores:
            return {}
        vals = np.array(list(scores.values()), dtype=float)
        vals = np.nan_to_num(vals)
        mean, std = vals.mean(), vals.std()
        if std < 1e-8:
            return {s: 0.0 for s in scores}
        return {s: float((v - mean) / std) for s, v in zip(scores.keys(), vals)}

    def _get_death_risks(self, snapshots, db):
        try:
            from app.ml.death_risk.train import predict_death_risk
            symbols = [snapshot.symbol for snapshot in snapshots]
            return predict_death_risk(symbols, db, resolve_artifact_dir(settings.ml_death_risk_artifact_dir))
        except Exception:
            return {s.symbol: 0.0 for s in snapshots}

    def score(self, snapshots, db):
        lgb_preds, lgb_info = self.lgb_predictor.predict(snapshots)
        if not lgb_preds:
            return {}, {
                "available": False,
                "model_source": "RULES",
                "active_mode": "rules_only",
                "components": self.component_status,
                "available_components": [name for name in ("lightgbm", "lstm", "gnn", "death_risk") if self.component_status[name]["available"]],
                "missing_components": [name for name in ("lightgbm", "lstm", "gnn", "death_risk") if not self.component_status[name]["available"]],
                "reason": lgb_info.get("reason", "lightgbm_unavailable"),
                "artifact_classification": "missing",
            }

        lgb_z = self._zscore({sym: float(pred.pred_21d_return) for sym, pred in lgb_preds.items()})
        gnn_raw = {snapshot.symbol: float(np.mean(self._gnn_embeddings[snapshot.symbol][:4])) for snapshot in snapshots if snapshot.symbol in self._gnn_embeddings}
        gnn_z = self._zscore(gnn_raw)
        lstm_raw = self._get_lstm_scores(snapshots)
        lstm_z = self._zscore(lstm_raw)
        death_risks = self._get_death_risks(snapshots, db)

        available_components = ["lightgbm"]
        if lstm_z:
            available_components.append("lstm")
        if gnn_z:
            available_components.append("gnn")
        if any(abs(value) > 0 for value in death_risks.values()):
            available_components.append("death_risk")
        missing_components = [name for name in ("lightgbm", "lstm", "gnn", "death_risk") if name not in available_components]

        configured_weights = dict(self.ensemble_manifest.get("component_weights", {}))
        component_weights = {
            "lightgbm": float(configured_weights.get("lightgbm", 0.50)),
            "lstm": float(configured_weights.get("lstm", 0.25)),
            "gnn": float(configured_weights.get("gnn", 0.15)),
        }
        available_weight_sum = sum(weight for name, weight in component_weights.items() if name in available_components)
        normalized_weights = {
            name: (weight / available_weight_sum if name in available_components and available_weight_sum > 1e-9 else 0.0)
            for name, weight in component_weights.items()
        }
        death_risk_penalty = float(self.ensemble_manifest.get("death_risk_penalty", 1.5))

        results = {}
        top_model_drivers_by_symbol = {}
        for sym in lgb_z:
            lgb = lgb_z.get(sym, 0.0)
            lstm = lstm_z.get(sym, 0.0)
            gnn = gnn_z.get(sym, 0.0)
            death_risk = death_risks.get(sym, 0.0)
            pred_21d = (
                normalized_weights["lightgbm"] * lgb
                + normalized_weights["lstm"] * lstm
                + normalized_weights["gnn"] * gnn
            )
            if "death_risk" in available_components:
                pred_21d -= death_risk_penalty * death_risk
            pred_annual = float(min(0.40, max(-0.20, (1.0 + pred_21d) ** (252 / 21) - 1.0)))
            drivers = list(lgb_preds[sym].top_drivers)
            if "lstm" in available_components:
                drivers.append(f"lstm_z={lstm:+.2f}")
            if "gnn" in available_components:
                drivers.append(f"gnn_z={gnn:+.2f}")
            if "death_risk" in available_components:
                drivers.append(f"death_risk={death_risk:.2f}")
            top_model_drivers_by_symbol[sym] = drivers
            results[sym] = MLPrediction(
                pred_21d_return=round(pred_21d, 4),
                pred_annual_return=round(pred_annual, 4),
                top_drivers=drivers,
                component_scores={
                    "lightgbm_z": round(lgb, 4),
                    "lstm_z": round(lstm, 4),
                    "gnn_z": round(gnn, 4),
                    "death_risk": round(death_risk, 4),
                },
            )

        return results, {
            "available": True,
            "ensemble": True,
            "model_source": "ENSEMBLE",
            "active_mode": "full_ensemble" if not missing_components else "degraded_ensemble",
            "components": self.component_status,
            "available_components": available_components,
            "missing_components": missing_components,
            "component_weights": normalized_weights,
            "death_risk_penalty": death_risk_penalty,
            "model_version": str(self.ensemble_manifest.get("model_version") or lgb_info.get("model_version", "ensemble_v1_default")),
            "prediction_horizon_days": int(self.ensemble_manifest.get("prediction_horizon_days") or lgb_info.get("prediction_horizon_days", 21)),
            "artifact_classification": str(self.ensemble_manifest.get("artifact_classification", "bootstrap")),
            "top_model_drivers_by_symbol": top_model_drivers_by_symbol,
        }
