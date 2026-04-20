from __future__ import annotations
import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.ml.lstm_alpha.train import train_lstm_walk_forward, save_lstm_model, LSTMTrainConfig
from app.ml.lstm_alpha.features import build_lstm_dataset_from_db, normalize_lstm_features
from app.ml.lstm_alpha.train import load_and_prepare_lstm_data
from app.models.instrument import Instrument
from sqlalchemy import select
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--max-symbols", type=int, default=50)
    p.add_argument("--artifact-dir", default="artifacts/models/lstm_v1")
    p.add_argument("--seq-len", type=int, default=20)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--hidden-dim", type=int, default=32)
    p.add_argument("--initial-train-samples", type=int, default=500)
    return p.parse_args()

def main() -> None:
    args = parse_args()
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        logger.info("Step 1: Fetching symbols from DB...")
        rows = db.execute(
            select(Instrument.symbol)
            .where(Instrument.series == "EQ")
            .limit(args.max_symbols)
        ).all()
        symbols = [r[0] for r in rows]
        logger.info(f"Found {len(symbols)} symbols")

        logger.info("Step 2: Building decision dates (monthly)...")
        start = date.fromisoformat(args.start_date)
        end = date.fromisoformat(args.end_date)
        from app.models.daily_bar import DailyBar
        from app.models.instrument import Instrument as Inst
        cal_rows = db.execute(
            select(DailyBar.trade_date)
            .join(Inst, DailyBar.instrument_id == Inst.id)
            .where(Inst.symbol == symbols[0])
            .where(DailyBar.trade_date >= start)
            .where(DailyBar.trade_date <= end)
            .order_by(DailyBar.trade_date)
        ).all()
        cal_dates = [r[0] for r in cal_rows]
        month_last = {}
        for d in cal_dates:
            month_last[(d.year, d.month)] = d
        decision_dates = sorted(month_last.values())
        logger.info(f"Decision dates: {len(decision_dates)} monthly dates from {decision_dates[0]} to {decision_dates[-1]}")

        logger.info("Step 3: Building LSTM dataset from DB...")
        dataset_df = build_lstm_dataset_from_db(db, symbols, decision_dates)
        logger.info(f"Raw dataset: {len(dataset_df)} sequences")

        logger.info("Step 4: Normalizing features...")
        normalized_df, norm_stats = normalize_lstm_features(dataset_df)

        logger.info("Step 5: Preparing tensors...")
        seq_len = 20
        n_features = 4
        n = len(normalized_df)
        X = np.zeros((n, seq_len, n_features), dtype=np.float32)
        
        # Vectorized: avoid nested .iloc loop
        close_cols = [f'close_{j}' for j in range(seq_len)]
        volume_cols = [f'volume_{j}' for j in range(seq_len)]
        return_cols = [f'return_{j}' for j in range(seq_len)]
        hlr_cols = [f'high_low_ratio_{j}' for j in range(seq_len)]
        
        X[:, :, 0] = normalized_df[close_cols].values.astype(np.float32)
        X[:, :, 1] = normalized_df[volume_cols].values.astype(np.float32)
        X[:, :, 2] = normalized_df[return_cols].values.astype(np.float32)
        X[:, :, 3] = normalized_df[hlr_cols].values.astype(np.float32)
        
        y = normalized_df['target_21d'].values.astype(np.float32)
        logger.info(f"Tensor shape: X={X.shape}, y={y.shape}")

        logger.info("Step 6: Training LSTM...")
        config = LSTMTrainConfig(
            hidden_size=args.hidden_dim,
            epochs=args.epochs,
            device="cpu",
        )
        result = train_lstm_walk_forward(
            X=X,
            y=y,
            symbols=list(normalized_df['symbol']),
            decision_dates=list(normalized_df['decision_date'].astype(str)),
            config=config,
            initial_train_samples=args.initial_train_samples,
        )

        logger.info("Step 7: Saving artifacts...")
        model_config = {
            "seq_len": seq_len,
            "input_dim": n_features,
            "hidden_dim": args.hidden_dim,
            "num_layers": 2,
            "epochs": args.epochs,
        }
        save_lstm_model(result["model"], result["metrics"], model_config, artifact_dir)

        norm_stats_serializable = {k: list(v) for k, v in norm_stats.items()}
        with (artifact_dir / "norm_stats.json").open("w") as f:
            json.dump(norm_stats_serializable, f)

        metadata = {
            "model_version": "lstm_v1_" + datetime.now().strftime("%Y-%m-%d"),
            "trained_date": datetime.now().isoformat(),
            "total_sequences": len(X),
            "device": "cpu",
            "train_loss": result["metrics"].get("train_loss"),
            "val_mse": result["metrics"].get("val_mse"),
        }
        with (artifact_dir / "lstm_metadata.json").open("w") as f:
            json.dump(metadata, f, indent=2)

        logger.info("LSTM training complete!")
        logger.info(f"  train_loss = {result['metrics'].get('train_loss', 0):.4f}")
        logger.info(f"  val_mse    = {result['metrics'].get('val_mse', 0):.4f}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
