from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryMovement, MovementKind
from app.models.product import ProductVariant
from app.models.purchase import PurchaseOrderLine
from app.schemas.inventory_replenishment import (
    ReplenishmentLine,
    ReplenishmentSuggestion,
    StockAlert,
)
from app.services.exceptions import (
    InsufficientReservationError,
    InsufficientStockError,
    InvalidQuantityError,
)

_MOVEMENTS_READY_KEY = "inventory_movements_ready"


async def _ensure_movements_table(db: AsyncSession) -> None:
    if db.info.get(_MOVEMENTS_READY_KEY):
        return

    def _create_table(sync_session) -> None:
        InventoryMovement.__table__.create(bind=sync_session.bind, checkfirst=True)

    await db.run_sync(_create_table)
    db.info[_MOVEMENTS_READY_KEY] = True


async def _log_movement(
    db: AsyncSession,
    variant: ProductVariant,
    mtype: MovementKind,
    qty: int,
    reason: str | None,
) -> None:
    await _ensure_movements_table(db)
    movement = InventoryMovement(
        variant_id=variant.id,
        type=mtype,
        quantity=int(qty),
        reason=reason,
    )
    db.add(movement)
    await db.flush([movement])


async def _log_and_add_movement(
    db: AsyncSession,
    variant: ProductVariant,
    mtype: MovementKind,
    qty: int,
    reason: str | None,
) -> ProductVariant:
    """Helper para añadir la variante a la sesión y registrar el movimiento, sin commit."""
    db.add(variant)
    await db.flush([variant])
    await _log_movement(db, variant, mtype, qty, reason)
    return variant


async def receive_stock(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    reason: str | None = None,
) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    variant.stock_on_hand += quantity
    return await _log_and_add_movement(db, variant, MovementKind.RECEIVE, quantity, reason)


async def adjust_stock(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    reason: str | None = None,
) -> ProductVariant:
    new_on_hand = variant.stock_on_hand + quantity
    if new_on_hand < 0:
        raise InsufficientStockError("El stock no puede quedar en negativo.")
    variant.stock_on_hand = new_on_hand
    return await _log_and_add_movement(db, variant, MovementKind.ADJUST, abs(quantity), reason)


async def reserve_stock(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    reason: str | None = None,
) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    if variant.stock_reserved + quantity > variant.stock_on_hand:
        raise InsufficientStockError("No hay stock disponible suficiente para reservar la cantidad solicitada.")
    variant.stock_reserved += quantity
    return await _log_and_add_movement(db, variant, MovementKind.RESERVE, quantity, reason)


async def release_stock(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    reason: str | None = None,
) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    if quantity > variant.stock_reserved:
        raise InsufficientReservationError("No se puede liberar más stock del que está reservado.")
    variant.stock_reserved -= quantity
    return await _log_and_add_movement(db, variant, MovementKind.RELEASE, quantity, reason)


async def commit_sale(
    db: AsyncSession,
    variant: ProductVariant,
    quantity: int,
    reason: str | None = None,
) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")

    if quantity > variant.stock_on_hand:
        raise InsufficientStockError("No hay stock disponible suficiente para la venta.")

    consume_reserved = min(quantity, variant.stock_reserved)
    variant.stock_reserved -= consume_reserved
    variant.stock_on_hand -= quantity

    if variant.stock_on_hand < 0:
        raise InsufficientStockError("El stock no puede quedar en negativo.")

    return await _log_and_add_movement(db, variant, MovementKind.SALE, quantity, reason)


async def list_movements(
    db: AsyncSession,
    variant: ProductVariant,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    await _ensure_movements_table(db)
    stmt = (
        select(InventoryMovement)
        .where(InventoryMovement.variant_id == variant.id)
        .order_by(InventoryMovement.created_at.desc())
        .offset(int(offset))
        .limit(int(limit))
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(row.id),
            "type": row.type.value,
            "quantity": int(row.quantity),
            "reason": row.reason,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


def _available(variant: ProductVariant) -> int:
    return int(variant.stock_on_hand) - int(variant.stock_reserved)


async def compute_stock_alerts(
    db: AsyncSession,
    supplier_id: uuid.UUID | str | None = None,
) -> list[StockAlert]:
    stmt = select(ProductVariant)
    if supplier_id:
        sid = uuid.UUID(str(supplier_id))
        stmt = stmt.where(ProductVariant.primary_supplier_id == sid)
    variants = (await db.execute(stmt)).scalars().all()

    alerts: list[StockAlert] = []
    for variant in variants:
        avail = _available(variant)
        if avail <= int(variant.reorder_point):
            missing = max(0, int(variant.reorder_point) - avail)
            alerts.append(
                StockAlert(
                    variant_id=variant.id,
                    available=avail,
                    reorder_point=int(variant.reorder_point),
                    missing=missing,
                )
            )
    return alerts


async def _get_last_unit_cost(db: AsyncSession, variant_id: uuid.UUID) -> float | None:
    stmt = (
        select(PurchaseOrderLine.unit_cost)
        .where(PurchaseOrderLine.variant_id == variant_id)
        .order_by(PurchaseOrderLine.id.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    return float(row[0]) if row else None


async def compute_replenishment_suggestion(
    db: AsyncSession,
    supplier_id: uuid.UUID | str | None = None,
) -> ReplenishmentSuggestion:
    alerts = await compute_stock_alerts(db, supplier_id)
    lines: list[ReplenishmentLine] = []

    for alert in alerts:
        variant = await db.get(ProductVariant, alert.variant_id)
        if not variant:
            continue
        suggested = max(1, max(alert.missing, int(variant.reorder_qty or 0)))
        last_cost = await _get_last_unit_cost(db, alert.variant_id)

        lines.append(
            ReplenishmentLine(
                variant_id=alert.variant_id,
                suggested_qty=suggested,
                reason=f"available({alert.available}) <= reorder_point({alert.reorder_point})",
                last_unit_cost=last_cost,
            )
        )

    return ReplenishmentSuggestion(
        supplier_id=uuid.UUID(str(supplier_id)) if supplier_id else None,
        lines=sorted(lines, key=lambda line: str(line.variant_id)),
    )
