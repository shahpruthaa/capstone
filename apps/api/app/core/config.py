from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "NSE Atlas API"
    app_env: str = "development"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    cors_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/nse_portfolio"
    redis_url: str = "redis://localhost:6379/0"
    raw_data_dir: str = "../../data/raw"
    nse_archive_base_url: str = "https://nsearchives.nseindia.com/content/cm"
    ml_lightgbm_artifact_dir: str = "artifacts/models/lightgbm_v1"
    ml_lstm_artifact_dir: str = "artifacts/models/lstm_v1"
    ml_gnn_artifact_dir: str = "artifacts/models/gnn_v1"
    ml_death_risk_artifact_dir: str = "artifacts/models/death_risk_v1"
    ml_ensemble_artifact_dir: str = "artifacts/models/ensemble_v1"
    ml_model_loader_max_symbols: int = 50
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()
