from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Security, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.promotion import PromotionCreate, PromotionUpdate, PromotionRead
from app.services import promotion_service

router = APIRouter(prefix="/admin/promotions", tags=["admin-promotions"])


@router.post("", response_model=PromotionRead, status_code=status.HTTP_201_CREATED)
def create_promotion(
    payload: PromotionCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    promotion = promotion_service.create_promotion(db, payload)
    return PromotionRead.model_validate(promotion)


@router.get("", response_model=list[PromotionRead])
def list_promotions(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    promotions = promotion_service.list_promotions(db, status_filter)
    return [PromotionRead.model_validate(promo) for promo in promotions]


@router.patch("/{promotion_id}", response_model=PromotionRead)
def update_promotion(
    promotion_id: UUID,
    payload: PromotionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    promotion = promotion_service.update_promotion(db, promotion_id, payload)
    return PromotionRead.model_validate(promotion)


@router.post("/{promotion_id}/activate", response_model=PromotionRead)
def activate_promotion(
    promotion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    promotion = promotion_service.activate_promotion(db, promotion_id)
    return PromotionRead.model_validate(promotion)


@router.post("/{promotion_id}/deactivate", response_model=PromotionRead)
def deactivate_promotion(
    promotion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    promotion = promotion_service.deactivate_promotion(db, promotion_id)
    return PromotionRead.model_validate(promotion)
