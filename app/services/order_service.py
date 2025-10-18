from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import (
    Order,
    OrderLine,
    OrderStatus,
    PaymentStatus,
    ShippingStatus,
    Shipment,
)
from app.models.product import ProductVariant
from app.models.cart import Cart, CartStatus
from app.schemas.order import OrderCreate, OrderLineCreate, ShipmentCreate
from app.services.pricing import get_variant_effective_price
from app.services import inventory_service, notification_service
from app.services.exceptions import ServiceError


def _as_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid UUID for {field}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _recompute_totals(order: Order) -> None:
    subtotal = sum(float(line.line_total) for line in order.lines)
    order.subtotal_amount = subtotal
    order.total_amount = (
        subtotal
        - float(order.discount_amount or 0)
        + float(order.shipping_amount or 0)
        + float(order.tax_amount or 0)
    )


def _reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        inventory_service.reserve_stock(db, variant, quantity, reason)
    except ServiceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.detail)


def _release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        inventory_service.release_stock(db, variant, quantity, reason)
    except ServiceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.detail)


def _commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        inventory_service.commit_sale(db, variant, quantity, reason)
    except ServiceError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.detail)


def create_order(db: Session, current_user_id: str | None, payload: OrderCreate) -> Order:
    order = Order(
        user_id=current_user_id,
        currency=payload.currency or "ARS",
        status=OrderStatus.draft,
        payment_status=PaymentStatus.pending,
        shipping_status=ShippingStatus.pending,
        shipping_amount=float(payload.shipping_amount or 0),
        tax_amount=float(payload.tax_amount or 0),
        discount_amount=float(payload.discount_amount or 0),
        shipping_address=payload.shipping_address,
        notes=payload.notes,
    )
    db.add(order)
    db.flush()

    try:
        for line in payload.lines:
            _add_line(db, order, line, reserve_stock=True)

        if order.lines:
            order.status = OrderStatus.pending_payment

        _recompute_totals(order)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    notification_service.notify_new_order(db, order)
    notification_service.notify_order_status(
        db,
        order,
        title="Orden creada",
        message="Tu orden ha sido creada y está pendiente de pago.",
    )
    return order


def _add_line(db: Session, order: Order, line: OrderLineCreate, *, reserve_stock: bool) -> OrderLine:
    variant = db.get(ProductVariant, _as_uuid(line.variant_id, "variant_id"))
    if not variant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant not found")

    unit_price = (
        float(line.unit_price)
        if line.unit_price is not None
        else get_variant_effective_price(db, variant)
    )

    order_line = OrderLine(
        order=order,
        variant_id=variant.id,
        quantity=line.quantity,
        unit_price=unit_price,
        line_total=unit_price * line.quantity,
    )
    db.add(order_line)
    db.flush()

    if reserve_stock and line.quantity > 0:
        _reserve_stock(db, variant, line.quantity, reason=f"order:{order.id}")

    return order_line


def add_line(db: Session, order: Order, line: OrderLineCreate) -> Order:
    if order.status not in [OrderStatus.draft, OrderStatus.pending_payment]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot modify lines in current status")

    try:
        _add_line(db, order, line, reserve_stock=True)
        _recompute_totals(order)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    notification_service.notify_new_order(db, order)
    notification_service.notify_order_status(
        db,
        order,
        title="Orden creada",
        message="Tu orden ha sido creada a partir del carrito.",
    )
    return order


def list_orders(
    db: Session,
    *,
    status_filter: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    shipping_status: ShippingStatus | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Order]:
    stmt = select(Order).order_by(Order.created_at.desc()).offset(offset).limit(limit)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if shipping_status:
        stmt = stmt.where(Order.shipping_status == shipping_status)
    if user_id:
        stmt = stmt.where(Order.user_id == user_id)

    return db.execute(stmt).scalars().all()


def get_order(db: Session, order_id: str) -> Order | None:
    return db.get(Order, _as_uuid(order_id, "order_id"))


def create_order_from_cart(db: Session, cart: Cart) -> Order:
    if cart.status != CartStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is not active")

    order = Order(
        user_id=cart.user_id,
        currency=cart.currency,
        status=OrderStatus.draft,
        payment_status=PaymentStatus.pending,
        shipping_status=ShippingStatus.pending,
        subtotal_amount=0,
        discount_amount=float(cart.discount_amount) if hasattr(cart, "discount_amount") else 0,
        shipping_amount=float(cart.shipping_amount) if hasattr(cart, "shipping_amount") else 0,
        total_amount=0,
    )
    db.add(order)
    db.flush()

    try:
        for item in cart.items:
            line_payload = OrderLineCreate(
                variant_id=item.variant_id,
                quantity=item.quantity,
                unit_price=float(item.unit_price),
            )
            _add_line(db, order, line_payload, reserve_stock=True)

        order.status = OrderStatus.pending_payment if order.lines else OrderStatus.draft
        _recompute_totals(order)

        cart.status = CartStatus.converted
        db.add(cart)

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    notification_service.notify_order_status(
        db,
        order,
        title="Pago acreditado",
        message="Tu pago fue recibido y la orden está confirmada.",
    )
    return order


def set_status_paid(db: Session, order: Order) -> Order:
    if order.status not in [OrderStatus.pending_payment, OrderStatus.draft]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order cannot be marked as paid")
    if order.total_amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order total must be greater than 0")

    try:
        for line in order.lines:
            variant = db.get(ProductVariant, line.variant_id)
            if not variant:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant not found")
            _commit_sale(db, variant, line.quantity, reason=f"order:{order.id}")

        order.status = OrderStatus.paid
        order.payment_status = PaymentStatus.approved
        order.paid_at = _utcnow()
        db.add(order)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    notification_service.notify_order_status(
        db,
        order,
        title="Orden cancelada",
        message="Tu orden ha sido cancelada.",
    )
    return order


def cancel_order(db: Session, order: Order) -> Order:
    if order.status in [OrderStatus.fulfilled, OrderStatus.refunded, OrderStatus.cancelled]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Order cannot be cancelled")
    if order.status == OrderStatus.paid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Paid orders require a refund process")

    try:
        for line in order.lines:
            variant = db.get(ProductVariant, line.variant_id)
            if not variant:
                continue
            _release_stock(db, variant, line.quantity, reason=f"order:{order.id}")

        order.status = OrderStatus.cancelled
        order.payment_status = PaymentStatus.cancelled
        order.cancelled_at = _utcnow()
        db.add(order)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    notification_service.notify_order_status(
        db,
        order,
        title="Orden enviada",
        message="Tu orden fue despachada, revisa el seguimiento disponible.",
    )
    return order


def fulfill_order(db: Session, order: Order, payload: ShipmentCreate | None = None) -> Order:
    if order.status != OrderStatus.paid:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only paid orders can be fulfilled")

    shipment_status = ShippingStatus.shipped
    shipped_at = _utcnow()
    delivered_at = None

    if payload:
        if payload.delivered_at:
            shipment_status = ShippingStatus.delivered
            delivered_at = payload.delivered_at
        if payload.shipped_at:
            shipped_at = payload.shipped_at

    shipment = Shipment(
        order=order,
        status=shipment_status,
        carrier=payload.carrier if payload else None,
        tracking_number=payload.tracking_number if payload else None,
        shipped_at=shipped_at,
        delivered_at=delivered_at,
        address=payload.address if payload else None,
        notes=payload.notes if payload else None,
    )
    db.add(shipment)

    order.status = OrderStatus.fulfilled
    order.shipping_status = shipment_status
    order.fulfilled_at = delivered_at or shipped_at
    db.add(order)

    db.commit()
    db.refresh(order)
    return order
