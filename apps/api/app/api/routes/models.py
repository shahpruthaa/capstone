from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.model_overview import build_current_model_overview

router = APIRouter()


@router.get("/current")
def current_model(db: Session = Depends(get_db)) -> dict:
    return build_current_model_overview(db)

