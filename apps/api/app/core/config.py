from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NSE AI Portfolio Manager API"
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/nse_portfolio"
    redis_url: str = "redis://localhost:6379/0"
    raw_data_dir: str = "../../data/raw"
    nse_archive_base_url: str = "https://nsearchives.nseindia.com/content/cm"

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
