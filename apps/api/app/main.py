from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.ml.lightgbm_alpha.artifact_loader import get_lightgbm_model_status
from app.services.local_bootstrap import bootstrap_local_state


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first research backend for the NSE AI Portfolio Manager, including rule-based allocation, historical replay, and LightGBM hybrid inference.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def _startup_bootstrap_local_runtime() -> None:
    # Ensure the local schema exists and seed the DB from cached bhavcopy archives when needed.
    app.state.bootstrap_status = bootstrap_local_state()  # type: ignore[attr-defined]
    # Validate artifact availability early so UI can display whether ML hybrid is active.
    app.state.lightgbm_model_status = get_lightgbm_model_status()  # type: ignore[attr-defined]
    # Start auto-ingestion scheduler (runs daily at 16:15 IST after NSE market close)
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Scheduler not started: {e}")


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
        "health": "/healthz",
    }
