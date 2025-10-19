from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session_async import get_async_db
from app.schemas.exposure import ExposureResponse
from app.services import exposure_service

router = APIRouter(prefix="/exposure", tags=["exposure"])


@router.get("", response_model=ExposureResponse)
async def get_exposure(
    context: str = Query(..., min_length=2, max_length=50, description="Contexto del carrusel (home, category, personalized)"),
    user_id: Optional[str] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_async_db),
):
    """Obtiene un mix balanceado de productos para el carrusel solicitado.

    Respuesta ejemplo:
    {
      "context": "home",
      "mix": [
        {"product_id": "…", "reason": ["popular_70", "in_stock"], "badges": []},
        {"product_id": "…", "reason": ["cold_boost_30"], "badges": ["promo"] }
      ],
      "expires_at": "2025-10-18T12:00:00Z"
    }
    """

    response = await exposure_service.get_exposure(
        db,
        context=context,
        user_id=user_id,
        category_id=category_id,
        limit=limit,
    )
    return response


@router.post("/refresh", include_in_schema=False)
async def refresh_exposure(
    context: str,
    user_id: Optional[str] = None,
    category_id: Optional[UUID] = None,
    limit: int = 12,
    db: AsyncSession = Depends(get_async_db),
):
    payload = await exposure_service.build_exposure(
        db,
        context=context,
        user_id=user_id,
        category_id=category_id,
        limit=limit,
    )
    return payload


@router.delete("/cache", include_in_schema=False)
async def clear_cache(
    context: Optional[str] = None,
    user_id: Optional[str] = None,
    category_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_async_db),
):
    await exposure_service.clear_cache(db, context, user_id, category_id)
    return {"status": "cleared"}

