from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session_async import get_async_db
from app.services import scoring_service
from app.tasks.scoring import run_scoring_task

router = APIRouter(prefix="/internal/scoring", tags=["scoring"], include_in_schema=False)


@router.post("/run")
async def run_scoring(db: AsyncSession = Depends(get_async_db)):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        try:
            result = await scoring_service.run_scoring(db)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        return result
    async_result = run_scoring_task.delay()
    outcome = async_result.get(timeout=settings.TASK_RESULT_TIMEOUT)
    return outcome


@router.get("/rankings")
async def get_rankings(limit: int = 20, db: AsyncSession = Depends(get_async_db)):
    rankings = await scoring_service.get_latest_rankings(db, limit)
    return [
        {
            "product_id": str(r.product_id),
            "popularity_score": float(r.popularity_score),
            "cold_score": float(r.cold_score),
            "profit_score": float(r.profit_score),
            "exposure_score": float(r.exposure_score),
            "computed_at": r.updated_at,
        }
        for r in rankings
    ]
