from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.schemas.portfolio import BacktestRequest, UserMandate
from app.services.db_quant_engine import run_backtest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _balanced_10_stock_mandate() -> UserMandate:
    return UserMandate(
        investment_horizon_weeks="4-8",
        preferred_num_positions=10,
        allow_small_caps=False,
        risk_attitude="balanced",
    )


def _run_and_save_epoch(
    db,
    *,
    name: str,
    start_date: str,
    end_date: str,
    out_dir: Path,
) -> Path:
    payload = BacktestRequest(
        strategy_name=f"regime-epoch-{name}",
        start_date=start_date,
        end_date=end_date,
        mandate=_balanced_10_stock_mandate(),
        model_variant="LIGHTGBM_HYBRID",
        rebalance_frequency="QUARTERLY",
    )
    logger.info("Running regime epoch '%s' (%s -> %s)", name, start_date, end_date)
    result = run_backtest(db, payload)

    out_path = out_dir / f"{name}.json"
    with out_path.open("w", encoding="utf-8") as fp:
        json.dump(result.model_dump(mode="json"), fp, indent=2)
    logger.info("Saved %s", out_path)
    return out_path


def main() -> None:
    out_dir = Path("artifacts") / "backtests" / "regime_epochs"
    out_dir.mkdir(parents=True, exist_ok=True)

    epochs = [
        ("covid_crash", "2020-01-01", "2020-06-30"),
        ("rate_hike_correction", "2022-01-01", "2022-12-31"),
        ("bull_run", "2024-01-01", "2025-01-01"),
    ]

    db = SessionLocal()
    try:
        outputs = []
        for name, start_date, end_date in epochs:
            outputs.append(
                _run_and_save_epoch(
                    db,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    out_dir=out_dir,
                )
            )
        logger.info("Completed regime backtests: %s", ", ".join(str(path) for path in outputs))
    finally:
        db.close()


if __name__ == "__main__":
    main()
