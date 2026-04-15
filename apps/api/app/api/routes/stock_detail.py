"""Stock detail endpoint with ensemble signals, optional news context, and Groq explanation."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.groq_explainer import explain_stock
from app.services.model_runtime import get_model_runtime_status, resolve_artifact_dir

router = APIRouter()


@router.get("/{symbol}")
async def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    from app.ml.ensemble_alpha.predict import EnsembleAlphaPredictor
    from app.services.db_quant_engine import get_effective_trade_date, load_snapshots

    as_of_date = get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=90)
    snap = next((snapshot for snapshot in snapshots if snapshot.symbol == symbol), None)
    if snap is None:
        return {"error": f"No data found for {symbol}"}

    predictor = EnsembleAlphaPredictor()
    predictions, model_info = predictor.predict(db, snapshots, as_of_date)
    prediction = predictions.get(symbol)

    gnn_neighbors = []
    try:
        gnn_path = resolve_artifact_dir(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
        if gnn_path.exists():
            with gnn_path.open("r", encoding="utf-8") as handle:
                embeddings = json.load(handle)
            gnn_neighbors = [
                candidate.symbol
                for candidate in snapshots
                if candidate.symbol != symbol and candidate.symbol in embeddings and candidate.sector == snap.sector
            ][:5]
    except Exception:
        gnn_neighbors = []

    death_risk = 0.0
    try:
        from app.ml.death_risk.train import predict_death_risk

        death_risk_map = predict_death_risk([symbol], db, resolve_artifact_dir(settings.ml_death_risk_artifact_dir))
        death_risk = float(death_risk_map.get(symbol, 0.0))
    except Exception:
        death_risk = 0.0

    news_sentiment = 0.0
    try:
        from app.services.news_intelligence import get_market_context, get_stock_news_risk_score

        market_context = await get_market_context()
        news_sentiment = float(get_stock_news_risk_score(symbol, snap.sector, market_context))
    except Exception:
        news_sentiment = 0.0

    technicals = {
        "ret_21d": snap.factor_scores.get("momentum", 0.0),
        "ret_63d": getattr(snap, "ret_63d", 0.0),
        "vol_21d": snap.factor_scores.get("low_vol", 0.0),
        "dist_to_52w_high": getattr(snap, "dist_to_52w_high", 0.0),
        "beta_proxy": snap.beta_proxy,
        "market_cap_bucket": snap.market_cap_bucket or "Unknown",
    }
    drivers = list(prediction.top_drivers) if prediction else []
    explanation = explain_stock(
        symbol=symbol,
        sector=snap.sector or "Unknown",
        score=float(prediction.pred_21d_return) if prediction else 0.0,
        lgb_score=float(prediction.component_scores.get("lightgbm_z", 0.0)) if prediction else 0.0,
        lstm_score=float(prediction.component_scores.get("lstm_z", 0.0)) if prediction else 0.0,
        death_risk=death_risk,
        news_sentiment=news_sentiment,
        drivers=drivers,
        technicals=technicals,
        portfolio_context=f"NSE stock analysis as of {as_of_date}",
    )

    return {
        "symbol": symbol,
        "sector": snap.sector or "Unknown",
        "market_cap_bucket": snap.market_cap_bucket or "Unknown",
        "as_of_date": str(as_of_date),
        "active_mode": model_info.get("active_mode", "rules_only"),
        "model_version": model_info.get("model_version", "rules"),
        "artifact_classification": model_info.get("artifact_classification", "missing"),
        "ensemble_score": float(prediction.pred_21d_return) if prediction else 0.0,
        "pred_annual_return": float(prediction.pred_annual_return) if prediction else 0.0,
        "component_scores": prediction.component_scores if prediction else {},
        "death_risk": death_risk,
        "news_sentiment": news_sentiment,
        "feature_drivers": drivers,
        "gnn_sector_neighbors": gnn_neighbors,
        "factor_scores": snap.factor_scores,
        "beta": snap.beta_proxy,
        "explanation": explanation,
        "model_components": model_info.get("available_components", []),
        "runtime_status": get_model_runtime_status(),
    }
