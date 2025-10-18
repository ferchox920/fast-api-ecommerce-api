from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.promotion import Promotion, PromotionStatus, PromotionType
from app.schemas.promotion import PromotionCreate, PromotionUpdate
from app.services import notification_service
from app.services.event_bus import emit_promotion_event


def _is_time_active(promotion: Promotion, now: datetime) -> bool:
    return promotion.start_at <= now <= promotion.end_at


def create_promotion(db: Session, payload: PromotionCreate) -> Promotion:
    promotion = Promotion(
        name=payload.name,
        description=payload.description,
        type=PromotionType(payload.type),
        scope=payload.scope or "global",
        criteria_json=payload.criteria or {},
        benefits_json=payload.benefits or {},
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=PromotionStatus.draft,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return promotion


def list_promotions(db: Session, status_filter: Optional[str] = None):
    stmt = select(Promotion)
    if status_filter:
        stmt = stmt.where(Promotion.status == PromotionStatus(status_filter))
    return db.execute(stmt.order_by(Promotion.start_at.desc())).scalars().all()


def list_active_promotions(db: Session):
    now = datetime.now(timezone.utc)
    promotions = db.execute(
        select(Promotion).where(Promotion.status == PromotionStatus.active)
    ).scalars().all()
    return [promo for promo in promotions if _is_time_active(promo, now)]


def get_promotion(db: Session, promotion_id: UUID) -> Promotion:
    promotion = db.get(Promotion, promotion_id)
    if not promotion:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Promotion not found")
    return promotion


def update_promotion(db: Session, promotion_id: UUID, payload: PromotionUpdate) -> Promotion:
    promotion = get_promotion(db, promotion_id)
    if payload.name is not None:
        promotion.name = payload.name
    if payload.description is not None:
        promotion.description = payload.description
    if payload.scope is not None:
        promotion.scope = payload.scope
    if payload.criteria is not None:
        promotion.criteria_json = payload.criteria
    if payload.benefits is not None:
        promotion.benefits_json = payload.benefits
    if payload.start_at is not None:
        promotion.start_at = payload.start_at
    if payload.end_at is not None:
        promotion.end_at = payload.end_at
    if payload.status is not None:
        promotion.status = PromotionStatus(payload.status)
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return promotion


def activate_promotion(db: Session, promotion_id: UUID) -> Promotion:
    promotion = get_promotion(db, promotion_id)
    promotion.status = PromotionStatus.active
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    # INTEGRATION: Notificaciones (email/WS) consumirán 'promotion_start'; aquí invocamos adaptador directo.
    notification_service.notify_new_promotion(db, promotion)
    emit_promotion_event(
        "promotion_start",
        {
            "promotion_id": str(promotion.id),
            "name": promotion.name,
            "start_at": promotion.start_at.isoformat(),
            "end_at": promotion.end_at.isoformat(),
        },
    )
    return promotion


def deactivate_promotion(db: Session, promotion_id: UUID) -> Promotion:
    promotion = get_promotion(db, promotion_id)
    promotion.status = PromotionStatus.expired
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    emit_promotion_event(
        "promotion_end",
        {
            "promotion_id": str(promotion.id),
            "name": promotion.name,
        },
    )
    return promotion


def evaluate_eligibility(
    promotion: Promotion,
    *,
    user_id: Optional[str] = None,
    loyalty_level: Optional[str] = None,
    category_id: Optional[UUID] = None,
    product_id: Optional[UUID] = None,
    order_total: Optional[float] = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    now = datetime.now(timezone.utc)
    if promotion.start_at > now:
        reasons.append("not_started")
    if promotion.end_at < now:
        reasons.append("expired")
    if reasons:
        return False, reasons

    criteria = promotion.criteria_json or {}

    if promotion.scope == "category":
        required_categories = {str(cid) for cid in criteria.get("category_ids", [])}
        if required_categories and str(category_id) not in required_categories:
            return False, ["category_mismatch"]
    if promotion.scope == "product":
        required_products = {str(pid) for pid in criteria.get("product_ids", [])}
        if required_products and str(product_id) not in required_products:
            return False, ["product_scope_mismatch"]

    if promotion.type == PromotionType.customer:
        targeted = {pc.customer_id for pc in promotion.customers}
        if targeted and (not user_id or user_id not in targeted):
            return False, ["not_targeted"]

    loyalty_levels = criteria.get("loyalty_levels")
    if loyalty_levels and loyalty_level not in loyalty_levels:
        return False, ["loyalty_level_required"]

    min_order_total = criteria.get("min_order_total")
    if min_order_total and (order_total or 0) < min_order_total:
        return False, ["order_total_too_low"]

    # INTEGRATION: Checkout aplicará "benefits_json" (descuentos/cupones) y devolverá "applied_benefits".
    return True, ["eligible"]
