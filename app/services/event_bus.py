from __future__ import annotations

from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings


def emit_promotion_event(name: str, payload: dict[str, Any]) -> None:
    """Publish promotion events through the message broker."""
    task = celery_app.tasks.get("events.promotion")
    if task is None:
        raise RuntimeError("Promotion event task not registered")
    task.apply_async((name, payload), queue=settings.PROMOTION_EVENTS_QUEUE, ignore_result=True)


def emit_loyalty_event(name: str, payload: dict[str, Any]) -> None:
    """Publish loyalty events through the message broker."""
    task = celery_app.tasks.get("events.loyalty")
    if task is None:
        raise RuntimeError("Loyalty event task not registered")
    task.apply_async((name, payload), queue=settings.LOYALTY_EVENTS_QUEUE, ignore_result=True)
