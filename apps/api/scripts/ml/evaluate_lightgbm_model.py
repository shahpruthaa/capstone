from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", default="artifacts/models/lightgbm_v1")
    parser.add_argument("--report-dir", default="artifacts/reports")
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir)
    metrics_path = artifact_dir / "metrics.json"
    metadata_path = artifact_dir / "metadata.json"
    feature_manifest_path = artifact_dir / "feature_manifest.json"
    evaluation_report_path = artifact_dir / "evaluation_report.json"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing {metrics_path}")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    feature_manifest = json.loads(feature_manifest_path.read_text(encoding="utf-8")) if feature_manifest_path.exists() else {}
    avg_top_bottom_spread = metrics.get("avg_top_bottom_spread")
    if avg_top_bottom_spread is None:
        spreads = [
            float(fold["avg_top_bottom_spread"])
            for fold in metrics.get("folds", [])
            if isinstance(fold, dict) and fold.get("avg_top_bottom_spread") is not None
        ]
        avg_top_bottom_spread = (sum(spreads) / len(spreads)) if spreads else None

    report = json.loads(evaluation_report_path.read_text(encoding="utf-8")) if evaluation_report_path.exists() else {}
    if not report:
        report = {
            "model_version": feature_manifest.get("model_version", artifact_dir.name),
            "training_mode": metadata.get("training_mode", metrics.get("training_mode", "unknown")),
            "prediction_horizon_days": feature_manifest.get("prediction_horizon_days", 21),
            "validation_summary": {
                "best_avg_spearman_ic": metrics.get("best_avg_spearman_ic"),
                "avg_top_bottom_spread": avg_top_bottom_spread,
                "selection_status": metrics.get("selection_status"),
            },
            "folds": metrics.get("folds", []),
            "feature_count": len(feature_manifest.get("feature_order", [])),
            "feature_order": feature_manifest.get("feature_order", []),
        }
    else:
        report["validation_summary"] = {
            **report.get("validation_summary", {}),
            "best_avg_spearman_ic": report.get("validation_summary", {}).get("best_avg_spearman_ic", metrics.get("best_avg_spearman_ic")),
            "avg_top_bottom_spread": avg_top_bottom_spread,
            "selection_status": report.get("validation_summary", {}).get("selection_status", metrics.get("selection_status")),
        }
    evaluation_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    report_dir = Path(args.report_dir) / str(report.get("model_version", artifact_dir.name))
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = {
        "artifact_dir": str(artifact_dir),
        "report_path": str(report_dir / "evaluation_report.json"),
        "training_mode": report.get("training_mode"),
        "best_avg_spearman_ic": report.get("validation_summary", {}).get("best_avg_spearman_ic"),
        "avg_top_bottom_spread": report.get("validation_summary", {}).get("avg_top_bottom_spread"),
        "selection_status": report.get("validation_summary", {}).get("selection_status", metrics.get("selection_status")),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
