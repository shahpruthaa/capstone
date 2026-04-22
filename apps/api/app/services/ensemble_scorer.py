from __future__ import annotations
import json, logging
from pathlib import Path
from typing import Any
import numpy as np
from sqlalchemy.orm import Session
from app.core.config import settings
from app.ml.lightgbm_alpha.predict import LightGBMAlphaPredictor, MLPrediction

logger = logging.getLogger(__name__)
_SHARED_SCORER: "EnsembleScorer | None" = None

class EnsembleScorer:
    def __init__(self):
        self.lgb_predictor = LightGBMAlphaPredictor()
        self._gnn_embeddings = {}
        self._lstm_model = None
        self._lstm_norm_stats = {}
        self._load_gnn()
        self._load_lstm()

    def _load_gnn(self):
        try:
            path = Path(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
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
            base = Path(settings.ml_lstm_artifact_dir)
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

    def _get_death_risks(self, snapshots, db: Session):
        try:
            from app.ml.death_risk.train import predict_death_risk
            symbols = [snapshot.symbol for snapshot in snapshots]
            return predict_death_risk(
                symbols=symbols,
                db=db,
                artifact_dir=settings.ml_death_risk_artifact_dir,
            )
        except Exception:
            return {s.symbol: 0.0 for s in snapshots}

    def score(self, snapshots, db):
        lgb_preds, model_info = self.lgb_predictor.predict(snapshots)
        lgb_z   = self._zscore({sym: float(p.pred_21d_return) for sym, p in lgb_preds.items()})
        gnn_raw = {s.symbol: float(np.mean(self._gnn_embeddings[s.symbol][:4]))
                   for s in snapshots if s.symbol in self._gnn_embeddings}
        gnn_z   = self._zscore(gnn_raw)
        lstm_raw = self._get_lstm_scores(snapshots)
        lstm_z   = self._zscore(lstm_raw)
        death_risks = self._get_death_risks(snapshots, db)

        results = {}
        for sym in lgb_z:
            lgb  = lgb_z.get(sym, 0.0)
            gnn  = gnn_z.get(sym, 0.0)
            lstm = lstm_z.get(sym, 0.0)
            dr   = death_risks.get(sym, 0.0)
            # Weights: LGB 50%, LSTM 25%, GNN 15%, death_risk penalty
            f21  = (0.50 * lgb + 0.25 * lstm + 0.15 * gnn) - 1.5 * dr
            fan  = float(min(0.40, max(-0.20, (1.0 + f21) ** (252/21) - 1.0)))
            drivers = list(lgb_preds[sym].top_drivers) if sym in lgb_preds else []
            if lstm_z.get(sym) is not None:
                drivers.append(f"lstm={lstm:.2f}")
            drivers.append(f"death_risk={dr:.2f}")
            results[sym] = MLPrediction(
                pred_21d_return=round(f21, 4),
                pred_annual_return=round(fan, 4),
                top_drivers=drivers,
            )

        model_info["ensemble"] = True
        model_info["components"] = ["lightgbm", "lstm", "gnn", "death_risk"]
        return results, model_info


def get_shared_ensemble_scorer() -> EnsembleScorer:
    global _SHARED_SCORER
    if _SHARED_SCORER is None:
        _SHARED_SCORER = EnsembleScorer()
    return _SHARED_SCORER
