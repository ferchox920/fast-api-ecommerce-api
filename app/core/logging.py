from __future__ import annotations

import json
import logging
import logging.config
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

_STANDARD_ATTRS = set(logging.makeLogRecord({}).__dict__.keys())

class JsonFormatter(logging.Formatter):
    """Basic JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        message = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            message["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            message["stack_info"] = record.stack_info

        extra = {key: value for key, value in record.__dict__.items() if key not in _STANDARD_ATTRS}
        if extra:
            message["extra"] = extra

        return json.dumps(message, default=str)


def setup_logging() -> None:
    """Apply centralized logging configuration."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JsonFormatter,
            }
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "root": {
            "handlers": ["default"],
            "level": level,
        },
        "loggers": {
            "uvicorn.error": {"level": level},
            "uvicorn.access": {"handlers": ["default"], "level": level, "propagate": False},
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def security_alert(message: str, **context: Any) -> None:
    """Elevated security alert logs for downstream alerting rules."""
    logger = get_logger("app.security")
    logger.warning(message, extra={"alert": True, **context})
