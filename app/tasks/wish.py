from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.celery_app import celery_app
from app.db.session_async import AsyncSessionLocal
from app.services import wish_service


async def _evaluate(wish_id: UUID) -> dict:
    async with AsyncSessionLocal() as session:
        try:
            result = await wish_service.evaluate_wish(session, wish_id)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise


def _run(func, *args, **kwargs):
    return asyncio.run(func(*args, **kwargs))


@celery_app.task(name="wish.evaluate", ignore_result=True)
def evaluate_wish_task(wish_id: str) -> dict:
    return _run(_evaluate, UUID(wish_id))
