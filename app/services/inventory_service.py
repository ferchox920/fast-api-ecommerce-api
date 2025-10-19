from sqlalchemy.orm import Session
from sqlalchemy import select
import uuid

from app.models.inventory import InventoryMovement, MovementKind
from app.models.product import ProductVariant
from app.services.exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
    InsufficientReservationError,
)

# Clave para no repetir el ensure por sesión/bind
_MOVEMENTS_READY_KEY = "inventory_movements_ready"


def _ensure_movements_table(db: Session) -> None:
    """
    Garantiza que 'inventory_movements' exista usando la definición ORM.
    Se ejecuta solo una vez por bind gracias a db.info.
    """
    if db.info.get(_MOVEMENTS_READY_KEY):
        return

    InventoryMovement.__table__.create(bind=db.get_bind(), checkfirst=True)
    db.info[_MOVEMENTS_READY_KEY] = True


def _log_movement(db: Session, variant: ProductVariant, mtype: MovementKind, qty: int, reason: str | None) -> None:
    _ensure_movements_table(db)
    movement = InventoryMovement(variant_id=variant.id, type=mtype, quantity=int(qty), reason=reason)
    db.add(movement)
    db.flush([movement])


def _log_and_add_movement(
    db: Session,
    variant: ProductVariant,
    mtype: MovementKind,
    qty: int,
    reason: str | None,
) -> ProductVariant:
    """Helper para añadir la variante a la sesión y registrar el movimiento, sin commit."""
    db.add(variant)
    _log_movement(db, variant, mtype, qty, reason)
    return variant


def receive_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    variant.stock_on_hand += quantity
    return _log_and_add_movement(db, variant, MovementKind.RECEIVE, quantity, reason)


def adjust_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    new_on_hand = variant.stock_on_hand + quantity
    if new_on_hand < 0:
        raise InsufficientStockError("El stock no puede quedar en negativo.")
    variant.stock_on_hand = new_on_hand
    return _log_and_add_movement(db, variant, MovementKind.ADJUST, abs(quantity), reason)


def reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    if variant.stock_reserved + quantity > variant.stock_on_hand:
        raise InsufficientStockError("No hay stock disponible suficiente para reservar la cantidad solicitada.")
    variant.stock_reserved += quantity
    return _log_and_add_movement(db, variant, MovementKind.RESERVE, quantity, reason)


def release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")
    if quantity > variant.stock_reserved:
        raise InsufficientReservationError("No se puede liberar más stock del que está reservado.")
    variant.stock_reserved -= quantity
    return _log_and_add_movement(db, variant, MovementKind.RELEASE, quantity, reason)


def commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise InvalidQuantityError("La cantidad debe ser mayor que 0.")

    if quantity > variant.stock_on_hand:
        raise InsufficientStockError("No hay stock disponible suficiente para la venta.")

    consume_reserved = min(quantity, variant.stock_reserved)
    variant.stock_reserved -= consume_reserved
    variant.stock_on_hand -= quantity

    if variant.stock_on_hand < 0:
        raise InsufficientStockError("El stock no puede quedar en negativo.")

    return _log_and_add_movement(db, variant, MovementKind.SALE, quantity, reason)


def list_movements(db: Session, variant: ProductVariant, limit: int = 50, offset: int = 0):
    _ensure_movements_table(db)
    rows = (
        db.query(InventoryMovement)
        .filter(InventoryMovement.variant_id == variant.id)
        .order_by(InventoryMovement.created_at.desc())
        .offset(int(offset))
        .limit(int(limit))
        .all()
    )
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


# ========================
# Alerts & Replenishment
# ========================
from app.models.purchase import PurchaseOrderLine  # para último costo
from app.schemas.inventory_replenishment import (
    StockAlert,
    ReplenishmentSuggestion,
    ReplenishmentLine,
)


def _available(v: ProductVariant) -> int:
    return int(v.stock_on_hand) - int(v.stock_reserved)


def compute_stock_alerts(db: Session, supplier_id: uuid.UUID | str | None = None) -> list[StockAlert]:
    stmt = select(ProductVariant)
    if supplier_id:
        sid = uuid.UUID(str(supplier_id))
        stmt = stmt.where(ProductVariant.primary_supplier_id == sid)
    variants = db.execute(stmt).scalars().all()

    alerts: list[StockAlert] = []
    for v in variants:
        avail = _available(v)
        if avail <= int(v.reorder_point):
            missing = max(0, int(v.reorder_point) - avail)
            alerts.append(
                StockAlert(
                    variant_id=v.id,
                    available=avail,
                    reorder_point=int(v.reorder_point),
                    missing=missing,
                )
            )
    return alerts


def compute_replenishment_suggestion(db: Session, supplier_id: uuid.UUID | str | None = None) -> ReplenishmentSuggestion:
    alerts = compute_stock_alerts(db, supplier_id)
    lines: list[ReplenishmentLine] = []

    for a in alerts:
        v = db.get(ProductVariant, a.variant_id)
        suggested = max(1, max(a.missing, int(v.reorder_qty or 0)))
        last_cost = _get_last_unit_cost(db, a.variant_id)

        lines.append(
            ReplenishmentLine(
                variant_id=a.variant_id,
                suggested_qty=suggested,
                reason=f"available({a.available}) <= reorder_point({a.reorder_point})",
                last_unit_cost=last_cost,
            )
        )

    return ReplenishmentSuggestion(
        supplier_id=uuid.UUID(str(supplier_id)) if supplier_id else None,
        lines=sorted(lines, key=lambda line: str(line.variant_id)),
    )


def _get_last_unit_cost(db: Session, variant_id: uuid.UUID) -> float | None:
    row = (
        db.execute(
            select(PurchaseOrderLine.unit_cost)
            .where(PurchaseOrderLine.variant_id == variant_id)
            .order_by(PurchaseOrderLine.id.desc())
            .limit(1)
        ).first()
    )
    return float(row[0]) if row else None
