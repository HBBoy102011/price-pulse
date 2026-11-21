"""Application settings loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration.

    Every value can be overridden with an environment variable of the same
    name (case-insensitive) or via a local ``.env`` file.
    """

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PricePulse"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = f"sqlite:///{(BASE_DIR / 'pricepulse.db').as_posix()}"
    auto_create_tables: bool = True

    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "*"

    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Moscow"
    check_interval_hours: float = 6.0
    min_check_interval_minutes: int = 30

    request_timeout_seconds: float = 20.0
    max_concurrent_checks: int = 3
    request_delay_seconds: float = 0.4
    error_threshold: int = 3
    robots_check_enabled: bool = True

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = True

    default_user_telegram_id: int | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
