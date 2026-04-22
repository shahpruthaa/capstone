from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.ml.lightgbm_alpha.artifact_loader import get_lightgbm_model_status
from app.services.local_bootstrap import bootstrap_local_state
from app.services.scheduler import start_scheduler, stop_scheduler


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first AI portfolio research, backtesting, and trade intelligence for Indian markets.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def _startup_bootstrap_local_runtime() -> None:
    import logging

    logger = logging.getLogger(__name__)
    try:
        bootstrap_status = bootstrap_local_state()
        lightgbm_status = get_lightgbm_model_status()
        app.state.bootstrap_status = bootstrap_status  # type: ignore[attr-defined]
        app.state.lightgbm_model_status = lightgbm_status  # type: ignore[attr-defined]
        start_scheduler()
        logger.info("Startup bootstrap completed: %s", bootstrap_status)
        logger.info("LightGBM model status loaded: %s", lightgbm_status.get("available"))
    except Exception as error:
        logger.error("Startup error: %s", error, exc_info=True)
        raise


@app.on_event("shutdown")
def _shutdown_background_services() -> None:
    stop_scheduler()


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
        "health": "/healthz",
    }
