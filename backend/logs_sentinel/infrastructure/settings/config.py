from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    These settings are intentionally minimal for the MVP but structured so that
    they can be safely extended for production deployments.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="LOGS_SENTINEL_")

    environment: Literal["local", "dev", "prod"] = "local"

    # Core networking
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    db_url: str = Field(
        default="postgresql+asyncpg://logs_sentinel:logs_sentinel@postgres:5432/logs_sentinel",
        description="Async SQLAlchemy database URL.",
    )

    # Redis (cache, rate limiting, token store)
    redis_url: str = "redis://redis:6379/0"

    # Messaging (RabbitMQ / Celery broker and result backend)
    broker_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/1"

    # Security / auth
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_exp_minutes: int = 15
    refresh_token_exp_days: int = 7

    # CORS / frontend integration
    frontend_origin: AnyHttpUrl | None = Field(
        default=None,
        description="Primary frontend origin for CORS (e.g. production SPA URL).",
    )
    frontend_dev_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [
            AnyHttpUrl("http://localhost:5173"),
            AnyHttpUrl("http://127.0.0.1:5173"),
        ],
        description="Additional dev origins allowed for CORS.",
    )

    # Feature flags
    enable_llm_enrichment: bool = False
    openai_api_key: str | None = None

    # Plans / billing (config only)
    default_plan: Literal["monthly", "yearly", "unlimited"] = "monthly"
    monthly_events_limit: int = 1_000_000
    yearly_events_limit: int = 12_000_000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()


settings = get_settings()

