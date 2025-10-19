from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session_async import AsyncSessionLocal
from app.services import scoring_service


async def _run(window_days: int) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            result = await scoring_service.run_scoring(session, window_days)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


def _run_sync(window_days: int) -> dict:
    return asyncio.run(_run(window_days))


@celery_app.task(name="scoring.run")
def run_scoring_task(window_days: int | None = None) -> dict:
    return _run_sync(window_days or settings.SCORING_WINDOW_DAYS)
