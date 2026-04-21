from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session
from app.services.ensemble_scorer import EnsembleScorer
from app.ml.lightgbm_alpha.predict import MLPrediction

class EnsembleAlphaPredictor:
    def __init__(self):
        self.ensemble = EnsembleScorer()
        self.available = True

    def predict(self, db: Session, snapshots: list, decision_date: Any):
        try:
            return self.ensemble.score(snapshots, db)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Ensemble error: {e}", exc_info=True)
            return {}, {"available": False, "error": str(e)}
