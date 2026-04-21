from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.ml.lightgbm_alpha.artifact_loader import get_lightgbm_model_status
from app.services.local_bootstrap import bootstrap_local_state


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
        # Skip bootstrap on startup to avoid blocking the server
        # Ensure the local schema exists and seed the DB from cached bhavcopy archives when needed.
        logger.info("Bootstrapping will be done on-demand to avoid blocking startup")
        app.state.bootstrap_status = {"bootstrapped": False, "reason": "deferred"}  # type: ignore[attr-defined]
        app.state.lightgbm_model_status = {"available": False}  # type: ignore[attr-defined]
        logger.info("All startup tasks completed (deferred)")
    except Exception as e:
        logger.error(f"Startup error: {e}", exc_info=True)
        raise


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
        "health": "/healthz",
    }
