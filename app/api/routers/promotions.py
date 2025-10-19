from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session_async import get_async_db
from app.schemas.promotion import PromotionRead, PromotionEligibilityResponse
from app.services import promotion_service

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.get("/active", response_model=list[PromotionRead])
async def list_active_promotions(db: AsyncSession = Depends(get_async_db)):
    promotions = await promotion_service.list_active_promotions(db)
    return [PromotionRead.model_validate(promo, from_attributes=True) for promo in promotions]


@router.get("/{promotion_id}", response_model=PromotionRead)
async def get_promotion_detail(promotion_id: UUID, db: AsyncSession = Depends(get_async_db)):
    promo = await promotion_service.get_promotion(db, promotion_id)
    return PromotionRead.model_validate(promo, from_attributes=True)


@router.get("/{promotion_id}/eligibility", response_model=PromotionEligibilityResponse)
async def check_eligibility(
    promotion_id: UUID,
    user_id: Optional[str] = Query(default=None),
    loyalty_level: Optional[str] = Query(default=None),
    category_id: Optional[UUID] = Query(default=None),
    product_id: Optional[UUID] = Query(default=None),
    order_total: Optional[float] = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    promotion = await promotion_service.get_promotion(db, promotion_id)
    eligible, reasons = promotion_service.evaluate_eligibility(
        promotion,
        user_id=user_id,
        loyalty_level=loyalty_level,
        category_id=category_id,
        product_id=product_id,
        order_total=order_total,
    )
    return PromotionEligibilityResponse(promotion_id=promotion_id, eligible=eligible, reasons=reasons)
