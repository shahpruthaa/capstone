"""LSTM runtime: Load trained model and predict."""
from __future__ import annotations
import json
import logging
from pathlib import Path
import numpy as np
import torch
from app.ml.lstm_alpha.train import LSTMForecaster

logger = logging.getLogger(__name__)
LSTM_ARTIFACT_DIR = Path(__file__).parents[3] / "artifacts" / "models" / "lstm_v1"

class LSTMPredictor:
    def __init__(self, artifact_dir: Path | str = LSTM_ARTIFACT_DIR):
        self.artifact_dir = Path(artifact_dir)
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._load_model()
    
    def _load_model(self) -> None:
        model_path = self.artifact_dir / "lstm_model.pt"
        config_path = self.artifact_dir / "lstm_config.json"
        if not model_path.exists():
            logger.warning(f"LSTM model not found at {model_path}")
            return
        if not config_path.exists():
            logger.warning(f"LSTM config not found at {config_path}")
            return
        try:
            with config_path.open('r') as f:
                config_dict = json.load(f)
            self.model = LSTMForecaster(input_size=4, hidden_size=config_dict.get('hidden_size', 64), num_layers=config_dict.get('num_layers', 2), dropout=config_dict.get('dropout', 0.3), bidirectional=True).to(self.device)
            state_dict = torch.load(model_path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            logger.info(f"Loaded LSTM model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load LSTM model: {e}")
            self.model = None
    
    def predict(self, sequences: np.ndarray) -> np.ndarray:
        if self.model is None:
            logger.warning("LSTM model not loaded, returning zeros")
            return np.zeros(len(sequences))
        try:
            X_tensor = torch.tensor(sequences, dtype=torch.float32).to(self.device)
            with torch.no_grad():
                predictions = self.model(X_tensor).squeeze().cpu().numpy()
            if predictions.ndim == 0:
                predictions = np.array([predictions])
            return predictions
        except Exception as e:
            logger.error(f"LSTM prediction failed: {e}")
            return np.zeros(len(sequences))

def get_lstm_predictor() -> LSTMPredictor | None:
    if not hasattr(get_lstm_predictor, '_instance'):
        get_lstm_predictor._instance = LSTMPredictor()
        if get_lstm_predictor._instance.model is None:
            get_lstm_predictor._instance = None
    return get_lstm_predictor._instance
