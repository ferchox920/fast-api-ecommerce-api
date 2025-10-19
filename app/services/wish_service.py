from __future__ import annotations

from decimal import Decimal
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.promotion import Promotion, PromotionStatus, PromotionType
from app.models.wish import Wish, WishNotification, WishStatus
from app.schemas.wish import WishCreate
from app.services import notification_service


def _get_wish(db: Session, wish_id: UUID, user_id: str) -> Wish:
    wish = db.get(Wish, wish_id)
    if not wish or wish.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wish not found")
    return wish


def list_user_wishes(db: Session, user_id: str) -> Iterable[Wish]:
    stmt = select(Wish).where(Wish.user_id == user_id).order_by(Wish.created_at.desc())
    return db.execute(stmt).scalars().all()


def create_wish(db: Session, user_id: str, payload: WishCreate) -> Wish:
    existing = db.execute(
        select(Wish).where(Wish.user_id == user_id, Wish.product_id == payload.product_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Wish already exists for this product.")

    wish = Wish(
        user_id=user_id,
        product_id=payload.product_id,
        desired_price=payload.desired_price,
        notify_discount=payload.notify_discount,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)

    _enqueue_evaluation(str(wish.id))
    return wish


def delete_wish(db: Session, wish_id: UUID, user_id: str) -> None:
    wish = _get_wish(db, wish_id, user_id)
    db.delete(wish)
    db.commit()


def record_notification(db: Session, wish: Wish, notification_type: str, message: str) -> WishNotification:
    record = WishNotification(wish_id=wish.id, notification_type=notification_type, message=message)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _match_promotions(db: Session, wish: Wish) -> list[Promotion]:
    stmt = select(Promotion).where(Promotion.status == PromotionStatus.active, Promotion.type == PromotionType.product)
    promotions = db.execute(stmt).scalars().all()
    matches: list[Promotion] = []
    for promo in promotions:
        if not promo.criteria_json:
            continue
        product_ids = {UUID(pid) for pid in promo.criteria_json.get("product_ids", []) if pid}
        if wish.product_id in product_ids:
            matches.append(promo)
    return matches


def evaluate_wish(db: Session, wish_id: UUID) -> dict:
    wish = db.get(Wish, wish_id)
    if not wish or wish.status != WishStatus.active:
        return {"wish_id": str(wish_id), "notified": False}

    promotions = _match_promotions(db, wish)
    notified = False
    for promo in promotions:
        message = f"Tu deseo para el producto {wish.product_id} tiene una promoción activa: {promo.name}"
        record_notification(db, wish, "promotion", message)
        notification_service.create_notification(
            db,
            {
                "user_id": wish.user_id,
                "title": "Promoción disponible",
                "description": message,
                "data": {"promotion_id": str(promo.id), "product_id": str(wish.product_id)},
            },
            send_email=True,
        )
        notified = True

    if wish.notify_discount and wish.desired_price:
        current_price = _get_product_price(db, wish.product_id)
        if current_price is not None and current_price <= Decimal(wish.desired_price):
            message = (
                f"El producto de tu lista de deseos alcanzó el precio objetivo ({current_price} <= {wish.desired_price})."
            )
            record_notification(db, wish, "price_drop", message)
            notification_service.create_notification(
                db,
                {
                    "user_id": wish.user_id,
                    "title": "Precio objetivo alcanzado",
                    "description": message,
                    "data": {"product_id": str(wish.product_id)},
                },
                send_email=True,
            )
            notified = True

    return {"wish_id": str(wish_id), "notified": notified}


def _get_product_price(db: Session, product_id: UUID) -> Decimal | None:
    from app.models.product import Product  # local import to avoid cycle

    product = db.get(Product, product_id)
    return Decimal(product.price) if product and product.price is not None else None


def _enqueue_evaluation(wish_id: str) -> None:
    task = celery_app.tasks.get("wish.evaluate")
    if task is None:
        return
    task.apply_async(args=[wish_id], queue=settings.WISH_QUEUE, ignore_result=True)
