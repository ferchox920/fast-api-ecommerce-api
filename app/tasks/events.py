from __future__ import annotations

from app.core.celery_app import celery_app


@celery_app.task(name="events.promotion", ignore_result=True)
def handle_promotion_event(event_name: str, payload: dict) -> None:
    """Placeholder task to dispatch promotion events to downstream adapters."""
    print(f"[EVENT promotion] name={event_name} payload={payload}")


@celery_app.task(name="events.loyalty", ignore_result=True)
def handle_loyalty_event(event_name: str, payload: dict) -> None:
    """Placeholder task to dispatch loyalty events to downstream adapters."""
    print(f"[EVENT loyalty] name={event_name} payload={payload}")
