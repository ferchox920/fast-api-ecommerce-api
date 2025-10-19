from __future__ import annotations

from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.operations import flush_async, refresh_async, run_sync
from app.models.notification import NotificationType
from app.models.promotion import Promotion, PromotionStatus, PromotionType
from app.models.wish import Wish, WishNotification, WishStatus
from app.schemas.notification import NotificationCreate
from app.schemas.wish import WishCreate
from app.services import notification_service
from app.services.exceptions import ConflictError, ResourceNotFoundError


def _enqueue_evaluation(wish_id: str) -> None:
    task = celery_app.tasks.get("wish.evaluate")
    if task is None:
        return
    task.apply_async(args=[wish_id], queue=settings.WISH_QUEUE, ignore_result=True)


async def list_user_wishes(db: AsyncSession, user_id: str) -> Iterable[Wish]:
    stmt = select(Wish).where(Wish.user_id == user_id).order_by(Wish.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_wish(db: AsyncSession, user_id: str, payload: WishCreate) -> Wish:
    result = await db.execute(
        select(Wish).where(Wish.user_id == user_id, Wish.product_id == payload.product_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictError("Wish already exists for this product")

    wish = Wish(
        user_id=user_id,
        product_id=payload.product_id,
        desired_price=payload.desired_price,
        notify_discount=payload.notify_discount,
    )
    db.add(wish)
    await flush_async(db, wish)
    await refresh_async(db, wish)

    _enqueue_evaluation(str(wish.id))
    return wish


async def delete_wish(db: AsyncSession, wish_id: UUID, user_id: str) -> None:
    wish = await db.get(Wish, wish_id)
    if not wish or wish.user_id != user_id:
        raise ResourceNotFoundError("Wish not found")
    await db.delete(wish)


async def record_notification(
    db: AsyncSession, wish: Wish, notification_type: str, message: str
) -> WishNotification:
    record = WishNotification(wish_id=wish.id, notification_type=notification_type, message=message)
    db.add(record)
    await flush_async(db, record)
    await refresh_async(db, record)
    return record


async def _match_promotions(db: AsyncSession, wish: Wish) -> list[Promotion]:
    stmt = select(Promotion).where(
        Promotion.status == PromotionStatus.active,
        Promotion.type == PromotionType.product,
    )
    result = await db.execute(stmt)
    promotions = result.scalars().all()
    matches: list[Promotion] = []
    for promo in promotions:
        if not promo.criteria_json:
            continue
        product_ids = {UUID(pid) for pid in promo.criteria_json.get("product_ids", []) if pid}
        if wish.product_id in product_ids:
            matches.append(promo)
    return matches


async def evaluate_wish(db: AsyncSession, wish_id: UUID) -> dict:
    wish = await db.get(Wish, wish_id)
    if not wish or wish.status != WishStatus.active:
        return {"wish_id": str(wish_id), "notified": False}

    promotions = await _match_promotions(db, wish)
    notified = False
    for promo in promotions:
        message = f"Tu deseo para el producto {wish.product_id} tiene una promoción activa: {promo.name}"
        await record_notification(db, wish, "promotion", message)
        await run_sync(
            db,
            notification_service.create_notification,
            NotificationCreate(
                user_id=wish.user_id,
                type=NotificationType.promotion.value,
                title="Promoción disponible",
                message=message,
                payload={"promotion_id": str(promo.id), "product_id": str(wish.product_id)},
            ),
            send_email=True,
        )
        notified = True

    if wish.notify_discount and wish.desired_price:
        current_price = await _get_product_price(db, wish.product_id)
        if current_price is not None and current_price <= Decimal(wish.desired_price):
            message = (
                f"El producto de tu lista de deseos alcanzó el precio objetivo ({current_price} <= {wish.desired_price})."
            )
            await record_notification(db, wish, "price_drop", message)
            await run_sync(
                db,
                notification_service.create_notification,
                NotificationCreate(
                    user_id=wish.user_id,
                    type=NotificationType.promotion.value,
                    title="Precio objetivo alcanzado",
                    message=message,
                    payload={"product_id": str(wish.product_id)},
                ),
                send_email=True,
            )
            notified = True

    return {"wish_id": str(wish_id), "notified": notified}


async def _get_product_price(db: AsyncSession, product_id: UUID) -> Decimal | None:
    from app.models.product import Product

    product = await db.get(Product, product_id)
    if not product or product.price is None:
        return None
    return Decimal(str(product.price))
