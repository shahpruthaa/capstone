from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.lightgbm_alpha.predict import LightGBMAlphaPredictor, MLPrediction
from app.models.daily_bar import DailyBar
from app.models.instrument import Instrument
from app.services.model_runtime import load_ensemble_manifest, resolve_artifact_dir

logger = logging.getLogger(__name__)
_SHARED_SCORER: "EnsembleScorer | None" = None

LSTM_LOOKBACK = 20
LSTM_FETCH_BUFFER_DAYS = 65


class EnsembleScorer:
    def __init__(self):
        self.lgb_predictor = LightGBMAlphaPredictor()
        self._manifest = load_ensemble_manifest()
        self._gnn_embeddings: dict[str, list[float]] = {}
        self._lstm_model = None
        self._lstm_norm_stats: dict[str, list[float]] = {}
        self._load_gnn()
        self._load_lstm()

    def _load_gnn(self) -> None:
        try:
            path = resolve_artifact_dir(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
            if path.exists():
                with path.open() as f:
                    self._gnn_embeddings = json.load(f)
                logger.info("GNN embeddings loaded: %d symbols", len(self._gnn_embeddings))
        except Exception as exc:  # noqa: BLE001
            logger.warning("GNN load failed: %s", exc)

    def _load_lstm(self) -> None:
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

            with config_path.open() as f:
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
                with norm_path.open() as f:
                    self._lstm_norm_stats = json.load(f)

            logger.info("LSTM model loaded into ensemble")
        except Exception as exc:  # noqa: BLE001
            logger.warning("LSTM load failed: %s", exc)

    @staticmethod
    def _zscore(scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return {}
        vals = np.array(list(scores.values()), dtype=float)
        vals = np.nan_to_num(vals)
        mean_val, std_val = vals.mean(), vals.std()
        if std_val < 1e-8:
            return {symbol: 0.0 for symbol in scores}
        return {symbol: float((value - mean_val) / std_val) for symbol, value in zip(scores.keys(), vals)}

    @staticmethod
    def _resolve_as_of_date(snapshots: list[Any]) -> date | None:
        explicit = next((getattr(snapshot, "as_of_date", None) for snapshot in snapshots if getattr(snapshot, "as_of_date", None) is not None), None)
        if explicit is not None:
            return explicit
        latest_dates = [getattr(snapshot, "latest_trade_date", None) for snapshot in snapshots if getattr(snapshot, "latest_trade_date", None) is not None]
        return max(latest_dates) if latest_dates else None

    @staticmethod
    def _resolve_regime_name(snapshots: list[Any]) -> str:
        raw_regime = next((getattr(snapshot, "regime_name", None) for snapshot in snapshots if getattr(snapshot, "regime_name", None)), None)
        if not raw_regime:
            return "Neutral"
        normalized = str(raw_regime).strip().lower()
        if normalized == "bull":
            return "Bull"
        if normalized == "bear":
            return "Bear"
        return "Neutral"

    @staticmethod
    def _regime_weights(regime_name: str) -> tuple[float, float, float, float]:
        if regime_name == "Bull":
            return 0.50, 0.35, 0.15, 1.0
        if regime_name == "Bear":
            return 0.30, 0.10, 0.60, 2.5
        return 0.45, 0.25, 0.30, 1.5

    def _normalize_sequence_feature(self, values: list[float], prefix: str) -> list[float]:
        if not values:
            return []
        local_mean = float(sum(values) / len(values))
        local_std = float((sum((value - local_mean) ** 2 for value in values) / max(len(values), 1)) ** 0.5)
        if local_std <= 1e-8:
            local_std = 1.0

        normalized: list[float] = []
        for index, value in enumerate(values):
            stats = self._lstm_norm_stats.get(f"{prefix}_{index}") or self._lstm_norm_stats.get(f"{prefix}_0")
            if isinstance(stats, (list, tuple)) and len(stats) == 2:
                mean_val = float(stats[0])
                std_val = float(stats[1]) if abs(float(stats[1])) > 1e-8 else 1.0
            else:
                mean_val = local_mean
                std_val = local_std
            normalized.append((float(value) - mean_val) / std_val)
        return normalized

    def _fetch_lstm_window_bars(
        self,
        db: Session,
        symbols: list[str],
        as_of_date: date,
    ) -> dict[str, list[tuple[float, float, float, float]]]:
        if not symbols:
            return {}

        upper_symbols = sorted({symbol.upper() for symbol in symbols})
        start_date = as_of_date - timedelta(days=LSTM_FETCH_BUFFER_DAYS)

        rows = db.execute(
            select(
                Instrument.symbol,
                DailyBar.trade_date,
                DailyBar.close_price,
                DailyBar.high_price,
                DailyBar.low_price,
                DailyBar.total_traded_qty,
            )
            .join(Instrument, DailyBar.instrument_id == Instrument.id)
            .where(Instrument.symbol.in_(upper_symbols))
            .where(DailyBar.trade_date >= start_date)
            .where(DailyBar.trade_date <= as_of_date)
            .order_by(Instrument.symbol, DailyBar.trade_date)
        ).all()

        by_symbol: dict[str, list[tuple[float, float, float, float]]] = {symbol: [] for symbol in upper_symbols}
        for row in rows:
            volume = float(row.total_traded_qty) if row.total_traded_qty is not None else 0.0
            by_symbol[str(row.symbol).upper()].append((float(row.close_price), float(row.high_price), float(row.low_price), volume))
        return by_symbol

    def _get_lstm_scores(
        self,
        snapshots: list[Any],
        db: Session,
        as_of_date: date | None,
    ) -> dict[str, float]:
        if self._lstm_model is None or as_of_date is None:
            return {}

        try:
            import torch

            symbol_to_snapshot = {str(snapshot.symbol).upper(): snapshot for snapshot in snapshots}
            bars_by_symbol = self._fetch_lstm_window_bars(db, list(symbol_to_snapshot.keys()), as_of_date)
            scores: dict[str, float] = {}

            for symbol_upper, snapshot in symbol_to_snapshot.items():
                bars = bars_by_symbol.get(symbol_upper, [])
                if len(bars) < LSTM_LOOKBACK:
                    continue

                window = bars[-LSTM_LOOKBACK:]
                closes = [bar[0] for bar in window]
                highs = [bar[1] for bar in window]
                lows = [bar[2] for bar in window]
                volumes = [bar[3] for bar in window]

                returns = [0.0]
                for index in range(1, len(closes)):
                    prev_close = closes[index - 1]
                    returns.append((closes[index] / prev_close - 1.0) if abs(prev_close) > 1e-8 else 0.0)

                high_low_ratio = [
                    (highs[index] / lows[index]) if abs(lows[index]) > 1e-8 else 1.0
                    for index in range(len(closes))
                ]

                close_norm = self._normalize_sequence_feature(closes, "close")
                volume_norm = self._normalize_sequence_feature(volumes, "volume")
                return_norm = self._normalize_sequence_feature(returns, "return")
                hl_norm = self._normalize_sequence_feature(high_low_ratio, "high_low_ratio")

                seq = torch.zeros(1, LSTM_LOOKBACK, 4, dtype=torch.float32)
                for index in range(LSTM_LOOKBACK):
                    seq[0, index, 0] = close_norm[index]
                    seq[0, index, 1] = volume_norm[index]
                    seq[0, index, 2] = return_norm[index]
                    seq[0, index, 3] = hl_norm[index]

                with torch.no_grad():
                    pred = self._lstm_model(seq).item()
                scores[str(snapshot.symbol)] = float(pred)

            return scores
        except Exception as exc:  # noqa: BLE001
            logger.warning("LSTM inference failed: %s", exc)
            return {}

    def _get_death_risks(self, snapshots: list[Any], db: Session) -> dict[str, float]:
        try:
            from app.ml.death_risk.train import predict_death_risk

            symbols = [snapshot.symbol for snapshot in snapshots]
            return predict_death_risk(
                symbols=symbols,
                db=db,
                artifact_dir=str(resolve_artifact_dir(settings.ml_death_risk_artifact_dir)),
            )
        except Exception:  # noqa: BLE001
            return {snapshot.symbol: 0.0 for snapshot in snapshots}

    def score(self, snapshots: list[Any], db: Session) -> tuple[dict[str, MLPrediction], dict[str, Any]]:
        if not snapshots:
            return {}, {"available": False, "reason": "no_snapshots"}

        as_of_date = self._resolve_as_of_date(snapshots)
        regime_name = self._resolve_regime_name(snapshots)
        lgb_weight, lstm_weight, gnn_weight, death_risk_penalty = self._regime_weights(regime_name)

        lgb_preds, model_info = self.lgb_predictor.predict(snapshots)
        lgb_z = self._zscore({symbol: float(pred.pred_21d_return) for symbol, pred in lgb_preds.items()})

        gnn_raw = {
            snapshot.symbol: float(np.mean(self._gnn_embeddings[snapshot.symbol][:4]))
            for snapshot in snapshots
            if snapshot.symbol in self._gnn_embeddings
        }
        gnn_z = self._zscore(gnn_raw)

        lstm_raw = self._get_lstm_scores(snapshots, db, as_of_date)
        lstm_z = self._zscore(lstm_raw)

        death_risks = self._get_death_risks(snapshots, db)

        results: dict[str, MLPrediction] = {}
        for symbol in lgb_z:
            lgb_val = lgb_z.get(symbol, 0.0)
            gnn_val = gnn_z.get(symbol, 0.0)
            lstm_val = lstm_z.get(symbol, 0.0)
            dr_val = float(death_risks.get(symbol, 0.0))

            raw_score = (lgb_weight * lgb_val) + (lstm_weight * lstm_val) + (gnn_weight * gnn_val) - (death_risk_penalty * dr_val)
            # Component z-scores are ranks, not returns. Squash them into a plausible
            # 21-day return before annualizing so weak names are not all pegged to -20%.
            pred_21d = float(np.tanh(raw_score / 3.0) * 0.12)
            pred_annual = float(min(0.40, max(-0.20, (1.0 + pred_21d) ** (252 / 21) - 1.0)))

            drivers = list(lgb_preds[symbol].top_drivers) if symbol in lgb_preds else []
            drivers.append(
                f"regime={regime_name} w(lgb={lgb_weight:.2f},lstm={lstm_weight:.2f},gnn={gnn_weight:.2f},dr={death_risk_penalty:.2f})"
            )
            drivers.append(f"lgb_z={lgb_val:+.2f}")
            drivers.append(f"lstm={lstm_val:+.2f}")
            drivers.append(f"lstm_z={lstm_val:+.2f}")
            drivers.append(f"lstm_raw={float(lstm_raw.get(symbol, 0.0)):+.4f}")
            drivers.append(f"gnn_z={gnn_val:+.2f}")
            drivers.append(f"death_risk={dr_val:.2f}")
            drivers.append(f"ensemble_raw_score={raw_score:+.2f}")

            results[symbol] = MLPrediction(
                pred_21d_return=round(pred_21d, 4),
                pred_annual_return=round(pred_annual, 4),
                top_drivers=drivers,
            )

        non_zero_lstm = sum(1 for value in lstm_raw.values() if abs(value) > 1e-8)
        model_info["ensemble"] = True
        model_info["components"] = ["lightgbm", "lstm", "gnn", "death_risk"]
        model_info["regime_name"] = regime_name
        model_info["ensemble_weights"] = {
            "lightgbm": lgb_weight,
            "lstm": lstm_weight,
            "gnn": gnn_weight,
            "death_risk_penalty": death_risk_penalty,
        }
        model_info["lstm_nonzero_count"] = non_zero_lstm
        model_info["lstm_scored_symbols"] = sorted(lstm_raw.keys())
        model_info["model_version"] = str(self._manifest.get("model_version") or model_info.get("model_version", "ensemble"))
        model_info["prediction_horizon_days"] = int(self._manifest.get("prediction_horizon_days") or model_info.get("prediction_horizon_days", 21))
        return results, model_info


def get_shared_ensemble_scorer() -> EnsembleScorer:
    global _SHARED_SCORER
    if _SHARED_SCORER is None:
        _SHARED_SCORER = EnsembleScorer()
    return _SHARED_SCORER
