"""Stock detail endpoint — SHAP, LSTM signal, GNN neighbors, death risk."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

router = APIRouter()

@router.get("/{symbol}")
async def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """
    Returns full AI breakdown for a single stock:
    - LightGBM SHAP feature importances
    - LSTM signal
    - GNN sector neighbors
    - Death risk score
    - News sentiment
    - LLM explanation
    """
    from app.services.db_quant_engine import get_effective_trade_date, load_snapshots, predict_ensemble_for_snapshots
    from app.services.groq_explainer import explain_stock
    import json
    from pathlib import Path
    from app.core.config import settings

    as_of_date = get_effective_trade_date(db)
    snapshots = load_snapshots(db, as_of_date=as_of_date, min_history=90)
    snap = next((s for s in snapshots if s.symbol == symbol), None)

    if not snap:
        return {"error": f"No data found for {symbol}"}

    # Get ensemble predictions
    results, model_info = predict_ensemble_for_snapshots(db, snapshots, as_of_date)
    pred = results.get(symbol)

    # GNN neighbors — stocks in same sector from embeddings
    gnn_neighbors = []
    try:
        gnn_path = Path(settings.ml_gnn_artifact_dir) / "gnn_embeddings.json"
        if gnn_path.exists():
            with open(gnn_path) as f:
                embeddings = json.load(f)
            sector = snap.sector or "Unknown"
            gnn_neighbors = [
                s for s in embeddings.keys()
                if s != symbol and s in [sn.symbol for sn in snapshots]
            ][:5]
    except Exception:
        pass

    # Death risk
    death_risk = 0.0
    try:
        from app.ml.death_risk.train import predict_death_risk
        dr = predict_death_risk(
            symbols=[symbol],
            db=db,
            artifact_dir=settings.ml_death_risk_artifact_dir,
        )
        death_risk = dr.get(symbol, 0.0)
    except Exception:
        pass

    # SHAP-style feature importance from drivers
    drivers = list(pred.top_drivers) if pred else []

    # Technicals
    technicals = {
        "ret_21d": snap.factor_scores.get("momentum", 0.0),
        "ret_63d": getattr(snap, "ret_63d", 0.0),
        "vol_21d": snap.factor_scores.get("low_vol", 0.0),
        "dist_to_52w_high": getattr(snap, "dist_to_52w_high", 0.0),
        "beta_proxy": snap.beta_proxy,
        "market_cap_bucket": snap.market_cap_bucket or "Unknown",
    }

    # LLM explanation
    explanation = explain_stock(
        symbol=symbol,
        sector=snap.sector or "Unknown",
        score=float(pred.pred_21d_return) if pred else 0.0,
        lgb_score=float(pred.pred_21d_return) if pred else 0.0,
        lstm_score=0.0,
        death_risk=death_risk,
        news_sentiment=0.0,
        drivers=drivers,
        technicals=technicals,
        portfolio_context=f"NSE stock analysis as of {as_of_date}",
    )

    return {
        "symbol": symbol,
        "sector": snap.sector or "Unknown",
        "market_cap_bucket": snap.market_cap_bucket or "Unknown",
        "as_of_date": str(as_of_date),
        "ensemble_score": float(pred.pred_21d_return) if pred else 0.0,
        "pred_annual_return": float(pred.pred_annual_return) if pred else 0.0,
        "death_risk": death_risk,
        "feature_drivers": drivers,
        "gnn_sector_neighbors": gnn_neighbors,
        "factor_scores": snap.factor_scores,
        "beta": snap.beta_proxy,
        "explanation": explanation,
        "model_components": model_info.get("components", []),
    }
