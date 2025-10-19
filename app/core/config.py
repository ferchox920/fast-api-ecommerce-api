# app/core/config.py
"""Application configuration with strict environment validation."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Security & database ---
    SECRET_KEY: str = Field(..., min_length=16)
    REFRESH_SECRET_KEY: str | None = None
    DATABASE_URL: str = "sqlite:///./test.db"

    # --- Tokens ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 15
    VERIFY_TOKEN_EXPIRE_HOURS: int = 24
    ENFORCE_EMAIL_VERIFICATION: bool = True

    # --- API metadata ---
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "E-Commerce API"
    JWT_ALGORITHM: str = "HS256"

    # --- Emails ---
    EMAILS_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_TLS: bool = True
    EMAIL_FROM: str = "no-reply@example.com"

    # --- URLs ---
    API_BASE_URL: str = "http://127.0.0.1:8000"
    FRONTEND_URL: str = ""

    # --- Payments / Mercado Pago ---
    MERCADO_PAGO_ACCESS_TOKEN: str = ""
    MERCADO_PAGO_NOTIFICATION_URL: str = ""
    MERCADO_PAGO_SUCCESS_URL: str = ""
    MERCADO_PAGO_FAILURE_URL: str = ""
    MERCADO_PAGO_PENDING_URL: str = ""
    MERCADO_PAGO_WEBHOOK_SECRET: str = ""

    # --- Exposure engine defaults ---
    EXPOSURE_POPULARITY_WEIGHT: float = 0.7
    EXPOSURE_STRATEGIC_WEIGHT: float = 0.3
    EXPOSURE_CATEGORY_CAP: int = 3
    EXPOSURE_COLD_THRESHOLD: float = 0.6
    EXPOSURE_STOCK_THRESHOLD: int = 15
    EXPOSURE_FRESHNESS_THRESHOLD: float = 0.7
    EXPOSURE_CACHE_TTL: int = 600

    # --- Scoring defaults ---
    SCORING_WINDOW_DAYS: int = 14
    SCORING_HALF_LIFE_DAYS: float = 3.0
    SCORING_FRESHNESS_HALF_LIFE: float = 1.5

    # --- Celery / broker configuration ---
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "rpc://"
    CELERY_TASK_ALWAYS_EAGER: bool = True
    CELERY_TASK_DEFAULT_QUEUE: str = "default"
    EMAIL_QUEUE: str = "emails"
    REPORTS_QUEUE: str = "reports"
    SCORING_QUEUE: str = "scoring"
    PROMOTION_EVENTS_QUEUE: str = "promotion-events"
    LOYALTY_EVENTS_QUEUE: str = "loyalty-events"
    WISH_QUEUE: str = "wish-events"
    TASK_RESULT_TIMEOUT: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if not value or value.lower() == "changeme":
            raise ValueError("SECRET_KEY must be set to a non-default, secure value.")
        return value

    @property
    def refresh_secret_fallback(self) -> str:
        """Return the refresh secret or fallback to the main secret."""
        return self.REFRESH_SECRET_KEY or self.SECRET_KEY


settings = Settings()
