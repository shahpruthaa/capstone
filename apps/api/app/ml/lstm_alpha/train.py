"""LSTM Trainer: PyTorch LSTM for sequences."""
from __future__ import annotations
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.optim import Adam
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

class LSTMForecaster(nn.Module):
    def __init__(self, input_size: int = 4, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.3, bidirectional: bool = True):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0.0, bidirectional=bidirectional)
        lstm_out_size = hidden_size * (2 if bidirectional else 1)
        self.dense = nn.Sequential(nn.Linear(lstm_out_size, 32), nn.ReLU(), nn.Dropout(dropout), nn.Linear(32, 1))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        lstm_out, (h_n, c_n) = self.lstm(x)
        if self.bidirectional:
            h_final = torch.cat([h_n[-2], h_n[-1]], dim=1)
        else:
            h_final = h_n[-1]
        return self.dense(h_final)

@dataclass
class LSTMTrainConfig:
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.3
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 50
    weight_decay: float = 1e-5
    device: str = "cpu"
    early_stopping_patience: int = 10

def train_lstm_epoch(model: LSTMForecaster, train_loader: DataLoader, optimizer: torch.optim.Optimizer, device: str) -> float:
    model.train()
    total_loss = 0.0
    n_batches = 0
    criterion = nn.MSELoss()
    for X_batch, y_batch in train_loader:
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)
        optimizer.zero_grad()
        predictions = model(X_batch).squeeze()
        loss = criterion(predictions, y_batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1
    return total_loss / max(n_batches, 1)

def validate_lstm(model: LSTMForecaster, val_loader: DataLoader, device: str) -> tuple[float, float]:
    model.eval()
    criterion = nn.MSELoss()
    total_mse = 0.0
    total_mae = 0.0
    n_batches = 0
    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            predictions = model(X_batch).squeeze()
            mse = criterion(predictions, y_batch)
            mae = torch.abs(predictions - y_batch).mean()
            total_mse += mse.item()
            total_mae += mae.item()
            n_batches += 1
    avg_mse = total_mse / max(n_batches, 1)
    avg_mae = total_mae / max(n_batches, 1)
    return avg_mse, avg_mae

def train_lstm_walk_forward(X: np.ndarray, y: np.ndarray, symbols: list[str], decision_dates: list[str], config: LSTMTrainConfig = LSTMTrainConfig(), initial_train_samples: int = 500) -> dict[str, Any]:
    device = torch.device(config.device)
    n_samples = len(X)
    if initial_train_samples >= n_samples - 100:
        initial_train_samples = max(n_samples - 100, 50)
    logger.info(f"LSTM walk-forward training on {n_samples} samples")
    logger.info(f"Initial train set: {initial_train_samples}, rest for validation")
    model = LSTMForecaster(input_size=4, hidden_size=config.hidden_size, num_layers=config.num_layers, dropout=config.dropout, bidirectional=True).to(device)
    optimizer = Adam(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    X_train = torch.tensor(X[:initial_train_samples], dtype=torch.float32)
    y_train = torch.tensor(y[:initial_train_samples], dtype=torch.float32)
    X_val = torch.tensor(X[initial_train_samples:], dtype=torch.float32)
    y_val = torch.tensor(y[initial_train_samples:], dtype=torch.float32)
    train_loader = DataLoader(TensorDataset(X_train, y_train), batch_size=config.batch_size, shuffle=True)
    val_loader = DataLoader(TensorDataset(X_val, y_val), batch_size=config.batch_size, shuffle=False)
    best_val_mse = float('inf')
    patience_counter = 0
    for epoch in range(config.epochs):
        train_loss = train_lstm_epoch(model, train_loader, optimizer, device)
        val_mse, val_mae = validate_lstm(model, val_loader, device)
        if (epoch + 1) % 10 == 0:
            logger.info(f"Epoch {epoch+1}/{config.epochs}: train_loss={train_loss:.4f}, val_mse={val_mse:.4f}, val_mae={val_mae:.4f}")
        if val_mse < best_val_mse:
            best_val_mse = val_mse
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= config.early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break
    return {'model': model, 'metrics': {'train_loss': float(train_loss), 'val_mse': float(best_val_mse), 'val_mae': float(val_mae), 'epochs_trained': epoch + 1}, 'config': asdict(config)}

def load_and_prepare_lstm_data(csv_path: str) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    df = pd.read_csv(csv_path)
    n_samples = len(df)
    seq_len = 20
    n_features = 4
    X = np.zeros((n_samples, seq_len, n_features), dtype=np.float32)
    for i in range(n_samples):
        for j in range(seq_len):
            X[i, j, 0] = df.iloc[i][f'close_{j}']
            X[i, j, 1] = df.iloc[i][f'volume_{j}']
            X[i, j, 2] = df.iloc[i][f'return_{j}']
            X[i, j, 3] = df.iloc[i][f'high_low_ratio_{j}']
    y = df['target_21d'].values.astype(np.float32)
    symbols = df['symbol'].tolist()
    decision_dates = df['decision_date'].tolist()
    return X, y, symbols, decision_dates

def save_lstm_model(model: LSTMForecaster, metrics: dict[str, Any], config: dict[str, Any], artifact_dir: str | Path) -> None:
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_path = artifact_dir / "lstm_model.pt"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Saved LSTM model to {model_path}")
    config_path = artifact_dir / "lstm_config.json"
    with config_path.open('w') as f:
        json.dump(config, f, indent=2)
    metrics_path = artifact_dir / "lstm_metrics.json"
    with metrics_path.open('w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Saved LSTM artifacts to {artifact_dir}")
