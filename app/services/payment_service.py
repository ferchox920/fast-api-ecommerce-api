from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import run_sync
from app.models.order import (
    Order,
    OrderStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from app.services import order_service
from app.services.payment_providers import (
    PaymentProviderConfigurationError,
    PaymentProviderError,
    mercado_pago,
)


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


def _map_mp_status(value: str | None) -> PaymentStatus:
    if not value:
        return PaymentStatus.pending
    return MERCADO_PAGO_STATUS_MAP.get(value, PaymentStatus.pending)


async def create_payment_preference(db: AsyncSession, order: Order) -> Payment:
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
    await db.flush()
    await db.refresh(payment)
    await db.refresh(order)
    return payment


async def handle_mercado_pago_webhook(db: AsyncSession, payload: dict) -> None:
    data = payload.get("data") or {}
    payment_id = data.get("id") or payload.get("resource")
    if not payment_id:
        return

    def _get_payment_id(sync_db):
        record = (
            sync_db.query(Payment.id)
            .filter(Payment.provider_payment_id == str(payment_id))
            .limit(1)
            .first()
        )
        return record[0] if record else None

    stored_payment_id = await run_sync(db, _get_payment_id)
    if not stored_payment_id:
        return

    payment = await db.get(Payment, stored_payment_id)
    if not payment:
        return
    order = await order_service.get_order(db, str(payment.order_id))

    try:
        mp_payment = mercado_pago.get_payment(str(payment_id))
    except PaymentProviderError as exc:
        payment.last_webhook = payload
        payment.status_detail = f"error: {exc}"
        db.add(payment)
        await db.flush()
        return

    status_str = mp_payment.get("status")
    mp_status_detail = mp_payment.get("status_detail")

    payment.status = _map_mp_status(status_str)
    payment.status_detail = mp_status_detail
    payment.last_webhook = payload
    payment.provider_payment_id = str(mp_payment.get("id") or payment_id)

    if payment.status == PaymentStatus.approved and order.status != OrderStatus.paid:
        await db.flush()
        await order_service.set_status_paid(db, order)
    else:
        order.payment_status = payment.status
        db.add(order)
        db.add(payment)
    await db.flush()
    await db.refresh(payment)
    return payment
