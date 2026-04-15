from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize an ensemble manifest for the capstone runtime.")
    parser.add_argument("--artifact-dir", default="artifacts/models/ensemble_v1")
    parser.add_argument("--lightgbm-version", default="lightgbm_v1")
    parser.add_argument("--lstm-version", default="lstm_v1")
    parser.add_argument("--gnn-version", default="gnn_v1")
    parser.add_argument("--death-risk-version", default="death_risk_v1")
    parser.add_argument("--artifact-classification", default="standard", choices=["bootstrap", "standard"])
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "model_version": f"ensemble_v1_{date.today().isoformat()}",
        "artifact_classification": args.artifact_classification,
        "prediction_horizon_days": 21,
        "component_weights": {"lightgbm": 0.50, "lstm": 0.25, "gnn": 0.15},
        "death_risk_penalty": 1.5,
        "required_components": ["lightgbm"],
        "optional_components": ["lstm", "gnn", "death_risk"],
        "components": {
            "lightgbm": args.lightgbm_version,
            "lstm": args.lstm_version,
            "gnn": args.gnn_version,
            "death_risk": args.death_risk_version,
        },
        "training_mode": "standard",
    }

    manifest_path = artifact_dir / "ensemble_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    print(f"Wrote ensemble manifest to {manifest_path}")


if __name__ == "__main__":
    main()
