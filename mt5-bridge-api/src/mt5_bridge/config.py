"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the MT5 Bridge API.

    All fields are populated from environment variables or the .env file.
    Refer to .env.example for the full list of required variables.
    """

    # --- MetaTrader 5 ---
    mt5_login: int
    mt5_password: str
    mt5_server: str
    mt5_path: str | None = None
    mt5_timeout: int = 60_000

    # --- PostgreSQL ---
    db_url: str  # postgresql+asyncpg://user:pass@host:port/db

    # --- Application ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # --- OpenTelemetry (optional) ---
    otel_endpoint: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
