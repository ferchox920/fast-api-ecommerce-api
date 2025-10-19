# app/core/config.py
"""Application configuration with strict environment validation."""

from pathlib import Path

from pydantic import Field, field_validator, model_validator
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
    ASYNC_DATABASE_URL: str | None = None
    REDIS_URL: str | None = None
    SECRET_KEY_FALLBACKS: list[str] = Field(default_factory=list)
    REFRESH_SECRET_KEY_FALLBACKS: list[str] = Field(default_factory=list)
    JWT_BLACKLIST_ENABLED: bool = False
    JWT_BLACKLIST_TTL_LEEWAY_SECONDS: int = 300
    LOG_LEVEL: str = "INFO"
    METRICS_ENABLED: bool = True
    METRICS_NAMESPACE: str = "fastapi"
    METRICS_LATENCY_BUCKETS: list[float] = Field(default_factory=lambda: [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0])
    STRICT_TRANSPORT_SECURITY: str = "max-age=63072000; includeSubDomains; preload"
    CONTENT_SECURITY_POLICY: str = "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
    X_FRAME_OPTIONS: str = "DENY"
    X_CONTENT_TYPE_OPTIONS: str = "nosniff"
    REFERRER_POLICY: str = "no-referrer"
    MAX_REQUEST_SIZE_BYTES: int = 2 * 1024 * 1024  # 2MB default

    # --- Tokens ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
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
    MERCADO_PAGO_WEBHOOK_TOLERANCE_SECONDS: int = 300
    MERCADO_PAGO_WEBHOOK_REPLAY_TTL_SECONDS: int = 86400

    # --- Exposure engine defaults ---
    EXPOSURE_POPULARITY_WEIGHT: float = 0.7
    EXPOSURE_STRATEGIC_WEIGHT: float = 0.3
    EXPOSURE_CATEGORY_CAP: int = 3
    EXPOSURE_COLD_THRESHOLD: float = 0.6
    EXPOSURE_STOCK_THRESHOLD: int = 15
    EXPOSURE_FRESHNESS_THRESHOLD: float = 0.7
    EXPOSURE_CACHE_TTL: int = 600

    # --- Rate limiting ---
    RATE_LIMIT_REGISTRATION_PER_MINUTE: int = 5
    RATE_LIMIT_REGISTRATION_WINDOW_SECONDS: int = 60
    RATE_LIMIT_REPORTS_PER_MINUTE: int = 30
    RATE_LIMIT_REPORTS_WINDOW_SECONDS: int = 60

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

    @staticmethod
    def _split_list(value: str | list[str] | None) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [item for item in value if isinstance(item, str) and item.strip()]

    @staticmethod
    def _split_float_list(value: str | list[float] | None) -> list[float]:
        if value is None:
            return []
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            floats: list[float] = []
            for item in items:
                try:
                    floats.append(float(item))
                except ValueError:
                    continue
            return floats
        floats = []
        for item in value:
            try:
                floats.append(float(item))
            except (TypeError, ValueError):
                continue
        return floats

    @field_validator("SECRET_KEY_FALLBACKS", "REFRESH_SECRET_KEY_FALLBACKS", mode="before")
    @classmethod
    def validate_fallbacks(cls, value: str | list[str] | None) -> list[str]:
        return cls._split_list(value)

    @field_validator("METRICS_LATENCY_BUCKETS", mode="before")
    @classmethod
    def validate_metric_buckets(cls, value: str | list[float] | None) -> list[float]:
        floats = cls._split_float_list(value)
        return floats or cls.model_fields["METRICS_LATENCY_BUCKETS"].default_factory()  # type: ignore[attr-defined]

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if not value or value.lower() == "changeme":
            raise ValueError("SECRET_KEY must be set to a non-default, secure value.")
        return value

    @field_validator("MAX_REQUEST_SIZE_BYTES")
    @classmethod
    def validate_request_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_REQUEST_SIZE_BYTES must be positive.")
        return value

    @model_validator(mode="after")
    def ensure_async_database_url(self) -> "Settings":
        """Ensure an async URL is always available."""
        if not self.ASYNC_DATABASE_URL:
            self.ASYNC_DATABASE_URL = self._derive_async_url(self.DATABASE_URL)
        return self

    @staticmethod
    def _derive_async_url(url: str) -> str:
        """Best-effort conversion from sync to async driver."""
        if "+asyncpg" in url or "+aiosqlite" in url:
            return url
        if url.startswith("sqlite"):
            return url.replace("sqlite", "sqlite+aiosqlite", 1)
        if "://" not in url:
            return url

        scheme, rest = url.split("://", 1)
        if scheme.startswith("postgres"):
            base = "postgresql"
            driver = None
            if "+" in scheme:
                base_part, driver_part = scheme.split("+", 1)
                base = "postgresql" if base_part.startswith("postgres") else base_part
                driver = driver_part
            if driver in (None, "", "psycopg", "psycopg2", "psycopg2cffi"):
                async_scheme = f"{base}+asyncpg"
            elif driver == "asyncpg":
                async_scheme = f"{base}+asyncpg"
            else:
                async_scheme = f"{base}+{driver}"
            return f"{async_scheme}://{rest}"

        return url

    @property
    def refresh_secret_fallback(self) -> str:
        """Return the refresh secret or fallback to the main secret."""
        return self.REFRESH_SECRET_KEY or self.SECRET_KEY


settings = Settings()
