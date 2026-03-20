from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
