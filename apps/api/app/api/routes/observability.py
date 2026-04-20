from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.observability import ObservabilityKpiResponse
from app.services.observability import get_observability_kpis


router = APIRouter()


@router.get("/kpis", response_model=ObservabilityKpiResponse)
def observability_kpis_endpoint(db: Session = Depends(get_db)) -> ObservabilityKpiResponse:
    return get_observability_kpis(db)