from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.operations import run_sync
from app.models.cart import Cart, CartStatus
from app.models.order import (
    Order,
    OrderLine,
    OrderStatus,
    PaymentStatus,
    ShippingStatus,
    Shipment,
)
from app.models.product import ProductVariant
from app.schemas.order import OrderCreate, OrderLineCreate, ShipmentCreate
from app.services import inventory_service, notification_service
from app.services.exceptions import (
    ConflictError,
    DomainValidationError,
    ResourceNotFoundError,
    ServiceError,
)
from app.services.pricing import get_variant_effective_price


def _as_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception as exc:
        raise DomainValidationError(f"Invalid UUID for {field}") from exc


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


async def _reserve_stock(db: AsyncSession, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        await run_sync(db, inventory_service.reserve_stock, variant, quantity, reason)
    except ServiceError as exc:
        raise ConflictError(exc.detail) from exc


async def _release_stock(db: AsyncSession, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        await run_sync(db, inventory_service.release_stock, variant, quantity, reason)
    except ServiceError as exc:
        raise ConflictError(exc.detail) from exc


async def _commit_sale(db: AsyncSession, variant: ProductVariant, quantity: int, reason: str | None) -> None:
    try:
        await run_sync(db, inventory_service.commit_sale, variant, quantity, reason)
    except ServiceError as exc:
        raise ConflictError(exc.detail) from exc


async def _load_order_eager(db: AsyncSession, order: Order) -> None:
    await db.refresh(order)
    await db.refresh(order, attribute_names=["lines"])
    await db.refresh(order, attribute_names=["payments"])
    await db.refresh(order, attribute_names=["shipments"])


async def list_orders(
    db: AsyncSession,
    *,
    status_filter: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    shipping_status: ShippingStatus | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Order]:
    stmt = (
        select(Order)
        .options(
        selectinload(Order.lines),
        selectinload(Order.payments),
        selectinload(Order.shipments),
        )
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if shipping_status:
        stmt = stmt.where(Order.shipping_status == shipping_status)
    if user_id:
        stmt = stmt.where(Order.user_id == user_id)

    result = await db.execute(stmt)
    orders = result.scalars().all()
    return orders


async def get_order(db: AsyncSession, order_id: str) -> Order:
    order = await db.get(
        Order,
        _as_uuid(order_id, "order_id"),
        options=[
            selectinload(Order.lines),
            selectinload(Order.payments),
            selectinload(Order.shipments),
        ],
    )
    if not order:
        raise ResourceNotFoundError("Order not found")
    return order


async def _add_line(
    db: AsyncSession,
    order: Order,
    payload: OrderLineCreate,
    *,
    reserve_stock: bool,
) -> OrderLine:
    variant = await db.get(ProductVariant, _as_uuid(payload.variant_id, "variant_id"))
    if not variant:
        raise ResourceNotFoundError("Variant not found")

    if reserve_stock:
        await _reserve_stock(db, variant, payload.quantity, reason=f"order:{order.id}")

    unit_price = payload.unit_price or await get_variant_effective_price(db, variant)

    line = OrderLine(
        order=order,
        variant_id=variant.id,
        quantity=payload.quantity,
        unit_price=unit_price,
        line_total=unit_price * payload.quantity,
    )
    db.add(line)
    await db.flush()
    return line


async def create_order(db: AsyncSession, current_user_id: str | None, payload: OrderCreate) -> Order:
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
    await db.flush()

    for line in payload.lines:
        await _add_line(db, order, line, reserve_stock=True)

    await db.refresh(order, attribute_names=["lines"])
    if order.lines:
        order.status = OrderStatus.pending_payment

    _recompute_totals(order)
    db.add(order)
    await db.flush()

    await run_sync(db, notification_service.notify_new_order, order)
    await run_sync(
        db,
        notification_service.notify_order_status,
        order,
        title="Orden creada",
        message="Tu orden ha sido creada y está pendiente de pago.",
    )
    await _load_order_eager(db, order)
    return order


async def add_line(db: AsyncSession, order: Order, payload: OrderLineCreate) -> Order:
    await _add_line(db, order, payload, reserve_stock=True)
    await db.refresh(order, attribute_names=["lines"])
    _recompute_totals(order)
    db.add(order)
    await db.flush()
    await _load_order_eager(db, order)
    return order


async def create_order_from_cart(db: AsyncSession, cart: Cart) -> Order:
    await db.refresh(cart, attribute_names=["items"])

    order = Order(
        user_id=cart.user_id,
        currency=cart.currency,
        status=OrderStatus.draft,
        payment_status=PaymentStatus.pending,
        shipping_status=ShippingStatus.pending,
        subtotal_amount=0,
        discount_amount=float(getattr(cart, "discount_amount", 0) or 0),
        shipping_amount=float(getattr(cart, "shipping_amount", 0) or 0),
        total_amount=0,
    )
    db.add(order)
    await db.flush()

    for item in cart.items:
        line_payload = OrderLineCreate(
            variant_id=item.variant_id,
            quantity=item.quantity,
            unit_price=float(item.unit_price),
        )
        await _add_line(db, order, line_payload, reserve_stock=True)

    await db.refresh(order, attribute_names=["lines"])
    order.status = OrderStatus.pending_payment if order.lines else OrderStatus.draft
    _recompute_totals(order)

    cart.status = CartStatus.converted
    db.add(cart)
    db.add(order)
    await db.flush()

    await run_sync(
        db,
        notification_service.notify_order_status,
        order,
        title="Pago acreditado",
        message="Tu pago fue recibido y la orden está confirmada.",
    )
    await _load_order_eager(db, order)
    return order


async def set_status_paid(db: AsyncSession, order: Order) -> Order:
    if order.status not in [OrderStatus.pending_payment, OrderStatus.draft]:
        raise ConflictError("Order cannot be marked as paid")
    if order.total_amount <= 0:
        raise DomainValidationError("Order total must be greater than 0")

    await db.refresh(order, attribute_names=["lines"])

    for line in order.lines:
        variant = await db.get(ProductVariant, line.variant_id)
        if not variant:
            raise ResourceNotFoundError("Variant not found")
        await _commit_sale(db, variant, line.quantity, reason=f"order:{order.id}")

    order.status = OrderStatus.paid
    order.payment_status = PaymentStatus.approved
    order.paid_at = _utcnow()
    db.add(order)
    await db.flush()

    await run_sync(
        db,
        notification_service.notify_order_status,
        order,
        title="Orden pagada",
        message="Tu orden ha sido pagada correctamente.",
    )
    await _load_order_eager(db, order)
    return order


async def cancel_order(db: AsyncSession, order: Order) -> Order:
    if order.status in [OrderStatus.fulfilled, OrderStatus.refunded, OrderStatus.cancelled]:
        raise ConflictError("Order cannot be cancelled")
    if order.status == OrderStatus.paid:
        raise ConflictError("Paid orders require a refund process")

    await db.refresh(order, attribute_names=["lines"])

    for line in order.lines:
        variant = await db.get(ProductVariant, line.variant_id)
        if not variant:
            continue
        await _release_stock(db, variant, line.quantity, reason=f"order:{order.id}")

    order.status = OrderStatus.cancelled
    order.payment_status = PaymentStatus.cancelled
    order.cancelled_at = _utcnow()
    db.add(order)
    await db.flush()

    await run_sync(
        db,
        notification_service.notify_order_status,
        order,
        title="Orden cancelada",
        message="Tu orden ha sido cancelada.",
    )
    await _load_order_eager(db, order)
    return order


async def fulfill_order(db: AsyncSession, order: Order, payload: ShipmentCreate | None = None) -> Order:
    if order.status != OrderStatus.paid:
        raise ConflictError("Only paid orders can be fulfilled")

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
    await db.flush()

    await run_sync(
        db,
        notification_service.notify_order_status,
        order,
        title="Orden enviada",
        message="Tu orden fue despachada, revisa el seguimiento disponible.",
    )
    await _load_order_eager(db, order)
    return order
