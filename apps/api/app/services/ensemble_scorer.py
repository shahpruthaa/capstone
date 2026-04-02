from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Any
import numpy as np
from sqlalchemy.orm import Session
from app.core.config import settings
from app.ml.lightgbm_alpha.predict import LightGBMAlphaPredictor, MLPrediction

logger = logging.getLogger(__name__)

class EnsembleScorer:
    def __init__(self):
        self.lgb_predictor = LightGBMAlphaPredictor()
        self._gnn_embeddings = {}
        self._load_gnn()

    def _load_gnn(self):
        try:
            path = Path(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
            if path.exists():
                with open(path) as f:
                    self._gnn_embeddings = json.load(f)
                logger.info(f"GNN embeddings loaded: {len(self._gnn_embeddings)} symbols")
        except Exception as e:
            logger.warning(f"GNN load failed: {e}")

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

    def _get_death_risks(self, snapshots):
        try:
            from app.ml.death_risk.train import predict_death_risk
            return predict_death_risk(snapshots, settings.ml_death_risk_artifact_dir)
        except Exception:
            return {s.symbol: 0.0 for s in snapshots}

    def score(self, snapshots, db):
        lgb_preds, model_info = self.lgb_predictor.predict(snapshots)
        lgb_z = self._zscore({sym: float(p.pred_21d_return) for sym, p in lgb_preds.items()})
        gnn_raw = {s.symbol: float(np.mean(self._gnn_embeddings[s.symbol][:4]))
                   for s in snapshots if s.symbol in self._gnn_embeddings}
        gnn_z = self._zscore(gnn_raw)
        death_risks = self._get_death_risks(snapshots)
        results = {}
        for sym in lgb_z:
            lgb = lgb_z.get(sym, 0.0)
            gnn = gnn_z.get(sym, 0.0)
            dr  = death_risks.get(sym, 0.0)
            f21 = (0.65 * lgb + 0.20 * gnn) - 1.5 * dr
            fan = float(min(0.40, max(-0.20, (1.0 + f21) ** (252/21) - 1.0)))
            drivers = list(lgb_preds[sym].top_drivers) if sym in lgb_preds else []
            drivers.append(f"death_risk={dr:.2f}")
            results[sym] = MLPrediction(pred_21d_return=round(f21,4),
                                        pred_annual_return=round(fan,4),
                                        top_drivers=drivers)
        model_info["ensemble"] = True
        model_info["components"] = ["lightgbm", "gnn", "death_risk"]
        return results, model_info
