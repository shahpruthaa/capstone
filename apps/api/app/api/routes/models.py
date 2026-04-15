from fastapi import APIRouter

from app.services.model_runtime import get_model_runtime_status

router = APIRouter()


@router.get("/current")
def current_model() -> dict:
    return get_model_runtime_status()

