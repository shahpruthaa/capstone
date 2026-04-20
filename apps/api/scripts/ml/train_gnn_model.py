from __future__ import annotations
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.ml.gnn_alpha.graph import build_sector_graph
from app.ml.gnn_alpha.train import train_gnn, save_gnn_artifacts
from app.services.instrument_master import INSTRUMENT_MASTER

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--max-symbols", type=int, default=50)
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--hidden-dim", type=int, default=32)
    p.add_argument("--out-dim", type=int, default=16)
    p.add_argument("--artifact-dir", default="artifacts/models/gnn_v1")
    args = p.parse_args()

    # Use instrument master symbols — these all have kno sectors
    symbols = list(INSTRUMENT_MASTER.keys())[:args.max_symbols]
    logger.info(f"Using {len(symbols)} symbols from instrument master")

    db = SessionLocal()
    try:
        logger.info("Step 2: Building sector graph...")
        graph = build_sector_graph(db, symbols)

        logger.info("Step 3: Training GNN...")
        result = train_gnn(
            graph=graph,
            epochs=args.epochs,
            hidden_dim=args.hidden_dim,
            out_dim=args.out_dim,
        )

        logger.info("Step 4: Saving artifacts...")
        save_gnn_artifacts(result, graph, args.artifact_dir)
        logger.info("GNN training complete!")
        logger.info(f"  final_loss = {result['loss']:.4f}")
        logger.info(f"  embeddings shape = {result['embeddings'].shape}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
