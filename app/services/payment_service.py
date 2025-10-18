from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.order import (
    Order,
    OrderStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from app.services.payment_providers import (
    PaymentProviderError,
    PaymentProviderConfigurationError,
)
from app.services.payment_providers import mercado_pago
from app.services import order_service


MERCADO_PAGO_STATUS_MAP = {
    "pending": PaymentStatus.pending,
    "in_process": PaymentStatus.pending,
    "authorized": PaymentStatus.authorized,
    "approved": PaymentStatus.approved,
    "rejected": PaymentStatus.rejected,
    "cancelled": PaymentStatus.cancelled,
    "refunded": PaymentStatus.refunded,
    "charged_back": PaymentStatus.refunded,
}


def _map_mp_status(value: Optional[str]) -> PaymentStatus:
    if not value:
        return PaymentStatus.pending
    return MERCADO_PAGO_STATUS_MAP.get(value, PaymentStatus.pending)


def create_payment_preference(db: Session, order: Order) -> Payment:
    if order.status not in [OrderStatus.pending_payment, OrderStatus.draft]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order is not ready to pay")
    if not order.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order has no items")

    try:
        preference = mercado_pago.create_checkout_preference(order)
    except PaymentProviderConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except PaymentProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    preference_id = preference.get("id") or preference.get("preference_id")

    payment = Payment(
        order=order,
        provider=PaymentProvider.mercado_pago,
        provider_payment_id=str(preference_id) if preference_id else None,
        status=PaymentStatus.pending,
        amount=float(order.total_amount),
        currency=order.currency,
        init_point=preference.get("init_point"),
        sandbox_init_point=preference.get("sandbox_init_point"),
        raw_preference=preference,
    )

    db.add(payment)
    order.payment_status = PaymentStatus.pending
    db.add(order)
    db.commit()
    db.refresh(payment)
    db.refresh(order)
    return payment


def handle_mercado_pago_webhook(db: Session, payload: dict) -> None:
    data = payload.get("data") or {}
    payment_id = data.get("id") or payload.get("resource")
    if not payment_id:
        return

    payment = db.query(Payment).filter(Payment.provider_payment_id == str(payment_id)).first()
    if not payment:
        return

    try:
        mp_payment = mercado_pago.get_payment(str(payment_id))
    except PaymentProviderError as exc:
        payment.last_webhook = payload
        payment.status_detail = f"error: {exc}"
        db.add(payment)
        db.commit()
        return

    status_str = mp_payment.get("status")
    mp_status_detail = mp_payment.get("status_detail")

    payment.status = _map_mp_status(status_str)
    payment.status_detail = mp_status_detail
    payment.last_webhook = payload
    payment.provider_payment_id = str(mp_payment.get("id") or payment_id)

    if payment.status == PaymentStatus.approved and payment.order.status != OrderStatus.paid:
        db.add(payment)
        db.flush()
        order_service.set_status_paid(db, payment.order)
        db.refresh(payment)
    else:
        payment.order.payment_status = payment.status
        db.add(payment.order)
        db.add(payment)
        db.commit()
        db.refresh(payment)
