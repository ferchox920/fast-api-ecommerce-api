"""Celery task definitions package."""

from app.tasks import email  # noqa: F401
from app.tasks import events  # noqa: F401
from app.tasks import reports  # noqa: F401
from app.tasks import scoring  # noqa: F401
from app.tasks import wish  # noqa: F401

__all__ = ["email", "events", "reports", "scoring", "wish"]
