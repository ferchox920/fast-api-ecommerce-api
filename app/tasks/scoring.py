from __future__ import annotations

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.services import scoring_service


@celery_app.task(name="scoring.run")
def run_scoring_task(window_days: int | None = None) -> dict:
    db = SessionLocal()
    try:
        return scoring_service.run_scoring(db, window_days or settings.SCORING_WINDOW_DAYS)
    finally:
        db.close()
