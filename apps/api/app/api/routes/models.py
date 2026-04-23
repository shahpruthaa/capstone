from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.model_overview import build_current_model_overview
from app.services.model_runtime import get_model_runtime_status

router = APIRouter()


@router.get("/current")
def current_model() -> dict:
    """Fast, DB-free artifact status check. Used by the UI to gate portfolio generation."""
    return get_model_runtime_status()


@router.get("/overview")
def model_overview(db: Session = Depends(get_db)) -> dict:
    """Full model overview including DB-backed current signals and validation metrics."""
    return build_current_model_overview(db)

