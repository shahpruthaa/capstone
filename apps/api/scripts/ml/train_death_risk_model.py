from __future__ import annotations
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.ml.death_risk.train import (
    build_death_risk_dataset,
    train_death_risk_classifier,
    save_death_risk_artifacts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--artifact-dir", default="artifacts/models/death_risk_v1")
    p.add_argument("--min-days-threshold", type=int, default=200)
    args = p.parse_args()

    db = SessionLocal()
    try:
        df = build_death_risk_dataset(db, min_days_threshold=args.min_days_threshold)
        result = train_death_risk_classifier(df)
        save_death_risk_artifacts(result, args.artifact_dir)
        logger.info(f"Death-risk model complete! AUC={result['cv_auc']:.4f}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
