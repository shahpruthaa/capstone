from fastapi import APIRouter

from app.ml.lightgbm_alpha.artifact_loader import get_lightgbm_model_status

router = APIRouter()


@router.get("/current")
def current_model() -> dict:
    return get_lightgbm_model_status()

