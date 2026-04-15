from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Анализ скважинной динамики API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]
    csv_data_path: Path = Path(__file__).resolve().parents[3] / "well_metrics_v9.csv"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
