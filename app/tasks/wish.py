from __future__ import annotations

from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services import wish_service


@celery_app.task(name="wish.evaluate", ignore_result=True)
def evaluate_wish_task(wish_id: str) -> None:
    db = SessionLocal()
    try:
        wish_service.evaluate_wish(db, UUID(wish_id))
    finally:
        db.close()
