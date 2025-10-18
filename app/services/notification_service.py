from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.notification_manager import manager as ws_manager
from app.models.notification import Notification, NotificationType
from app.models.order import Order
from app.models.product_question import ProductQuestion, ProductAnswer
from app.models.user import User
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.services import email_service


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def list_notifications(db: Session, user: User, limit: int = 50, offset: int = 0):
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def _get_user(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_notification(db: Session, data: NotificationCreate, *, send_email: bool = False) -> Notification:
    notification = Notification(
        user_id=data.user_id,
        type=NotificationType(data.type),
        title=data.title,
        message=data.message,
        payload=data.payload,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    payload = {
        "id": str(notification.id),
        "type": notification.type.value,
        "title": notification.title,
        "message": notification.message,
        "payload": notification.payload,
        "created_at": notification.created_at.isoformat(),
    }
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ws_manager.send_to_user(notification.user_id, payload))
    except RuntimeError:
        pass

    if send_email:
        user = _get_user(db, notification.user_id)
        if user and user.email:
            email_service.send_notification_email(
                to_email=user.email,
                subject=notification.title,
                message=notification.message,
            )

    return notification


def mark_read(db: Session, notification_id: str, user: User, payload: NotificationUpdate) -> Notification:
    try:
        notif_uuid = uuid.UUID(str(notification_id))
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid notification id")

    notification = db.get(Notification, notif_uuid)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.is_read = payload.is_read
    notification.read_at = _utcnow() if payload.is_read else None
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def notify_admin_new_question(db: Session, question: ProductQuestion) -> None:
    admins: Iterable[User] = (
        db.query(User)
        .filter(User.is_superuser == True)  # noqa: E712
        .all()
    )
    title = "Nueva pregunta de producto"
    message = f"Pregunta sobre producto {question.product_id}: {question.content[:140]}"
    for admin in admins:
        data = NotificationCreate(
            user_id=admin.id,
            type=NotificationType.product_question.value,
            title=title,
            message=message,
            payload={"question_id": str(question.id), "product_id": str(question.product_id)},
        )
        create_notification(db, data)


def notify_question_answer(db: Session, question: ProductQuestion, answer: ProductAnswer) -> None:
    if not question.user_id:
        return
    data = NotificationCreate(
        user_id=question.user_id,
        type=NotificationType.product_answer.value,
        title="Respuesta a tu pregunta",
        message=answer.content[:200],
        payload={
            "question_id": str(question.id),
            "answer_id": str(answer.id),
            "product_id": str(question.product_id),
        },
    )
    create_notification(db, data, send_email=True)


def notify_order_status(db: Session, order: Order, title: str, message: str) -> None:
    if not order.user_id:
        return
    data = NotificationCreate(
        user_id=order.user_id,
        type=NotificationType.order_status.value,
        title=title,
        message=message,
        payload={
            "order_id": str(order.id),
            "status": order.status.value,
            "payment_status": order.payment_status.value,
            "shipping_status": order.shipping_status.value,
        },
    )
    create_notification(db, data, send_email=True)


def notify_new_order(db: Session, order: Order) -> None:
    admins: Iterable[User] = (
        db.query(User)
        .filter(User.is_superuser == True)  # noqa: E712
        .all()
    )
    title = "Nueva orden creada"
    message = f"Orden {order.id} por total {order.total_amount}"
    for admin in admins:
        data = NotificationCreate(
            user_id=admin.id,
            type=NotificationType.new_order.value,
            title=title,
            message=message,
            payload={"order_id": str(order.id)},
        )
        create_notification(db, data)


def notify_new_promotion(db: Session, promotion) -> None:
    admins: Iterable[User] = (
        db.query(User)
        .filter(User.is_superuser == True)  # noqa: E712
        .all()
    )
    title = "Promocion activada"
    message = f"{promotion.name} activo hasta {promotion.end_at.date()}"
    for admin in admins:
        data = NotificationCreate(
            user_id=admin.id,
            type=NotificationType.promotion.value,
            title=title,
            message=message,
            payload={"promotion_id": str(promotion.id)},
        )
        create_notification(db, data)


def notify_loyalty_upgrade(db: Session, profile, previous_level: str) -> None:
    data = NotificationCreate(
        user_id=profile.customer_id,
        type=NotificationType.loyalty.value,
        title="Subiste de nivel",
        message=f"Bienvenido al nivel {profile.level} (antes {previous_level}).",
        payload={
            "level": profile.level,
            "previous_level": previous_level,
            "points": profile.points,
        },
    )
    create_notification(db, data, send_email=True)
