from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, select
from fastapi import HTTPException
import uuid

from app.models.product import ProductVariant

# Clave para no repetir el ensure por sesión/bind
_MOVEMENTS_READY_KEY = "inventory_movements_ready"

def _ensure_movements_table(db: Session) -> None:
    """
    Garantiza que 'inventory_movements' exista.
    - En SQLite: CREATE TABLE IF NOT EXISTS (sin migraciones).
    - En otros motores: usa Inspector.has_table(); si no existe, intenta crear
      con el modelo (si está disponible) y por último un CREATE TABLE defensivo.
    Se ejecuta solo 1 vez por bind/sesión gracias a db.info.
    """
    # Si ya lo hicimos para este bind, nos vamos
    if db.info.get(_MOVEMENTS_READY_KEY):
        return

    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "unknown")

    if dialect == "sqlite":
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id TEXT PRIMARY KEY,
                variant_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                reason VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.info[_MOVEMENTS_READY_KEY] = True
        return

    # Otros motores
    insp = inspect(bind)
    # has_table es más eficiente que get_table_names()
    if insp.has_table("inventory_movements"):
        db.info[_MOVEMENTS_READY_KEY] = True
        return

    # Intento 1: crear desde el modelo (si existe)
    try:
        from app.models.inventory import InventoryMovement
        InventoryMovement.__table__.create(bind=bind, checkfirst=True)
    except Exception:
        # Intento 2 (defensivo): DDL mínima portable
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id UUID PRIMARY KEY,
                variant_id UUID NOT NULL,
                quantity INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                reason VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    finally:
        db.info[_MOVEMENTS_READY_KEY] = True


def _log_movement(db: Session, variant: ProductVariant, mtype: str, qty: int, reason: str | None) -> None:
    _ensure_movements_table(db)
    db.execute(
        text("""
            INSERT INTO inventory_movements (id, variant_id, quantity, type, reason)
            VALUES (:id, :variant_id, :quantity, :type, :reason)
        """),
        {
            "id": str(uuid.uuid4()),
            "variant_id": str(variant.id),
            "quantity": int(qty),
            "type": mtype,
            "reason": reason,
        },
    )


def _commit_with_movement(
    db: Session,
    variant: ProductVariant,
    mtype: str,
    qty: int,
    reason: str | None,
) -> ProductVariant:
    """Helper para registrar movimiento + commit + refresh."""
    _log_movement(db, variant, mtype, qty, reason)
    db.commit()
    db.refresh(variant)
    return variant


def receive_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    variant.stock_on_hand += quantity
    db.add(variant)
    return _commit_with_movement(db, variant, "receive", quantity, reason)


def adjust_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    new_on_hand = variant.stock_on_hand + quantity
    if new_on_hand < 0:
        raise HTTPException(status_code=400, detail="No puede quedar negativo")
    variant.stock_on_hand = new_on_hand
    db.add(variant)
    # guardamos el módulo para el histórico (mantiene tu comportamiento previo)
    return _commit_with_movement(db, variant, "adjust", abs(quantity), reason)


def reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if variant.stock_reserved + quantity > variant.stock_on_hand:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para reservar")
    variant.stock_reserved += quantity
    db.add(variant)
    return _commit_with_movement(db, variant, "reserve", quantity, reason)


def release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if quantity > variant.stock_reserved:
        raise HTTPException(status_code=400, detail="No hay reservado suficiente")
    variant.stock_reserved -= quantity
    db.add(variant)
    return _commit_with_movement(db, variant, "release", quantity, reason)


def commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")

    # Debe existir stock suficiente total
    if quantity > variant.stock_on_hand:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para la venta")

    # Consumir reservado primero hasta donde alcance
    consume_reserved = min(quantity, variant.stock_reserved)
    variant.stock_reserved -= consume_reserved

    # Siempre descuenta del stock_on_hand el total vendido
    variant.stock_on_hand -= quantity

    if variant.stock_on_hand < 0:
        # guardrail extra (no debería suceder por el check anterior)
        raise HTTPException(status_code=400, detail="No puede quedar negativo")

    db.add(variant)
    return _commit_with_movement(db, variant, "sale", quantity, reason)


def list_movements(db: Session, variant: ProductVariant, limit: int = 50, offset: int = 0):
    rows = db.execute(
        text("""
            SELECT id, type, quantity, reason, created_at
            FROM inventory_movements
            WHERE variant_id = :variant_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "variant_id": str(variant.id),
            "limit": int(limit),
            "offset": int(offset),
        },
    ).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "type": r["type"],
            "quantity": int(r["quantity"]),
            "reason": r["reason"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ========================
# Alerts & Replenishment
# ========================
from app.models.purchase import PurchaseOrderLine  # para último costo
from app.schemas.inventory_replenishment import (
    StockAlert, ReplenishmentSuggestion, ReplenishmentLine
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
            alerts.append(StockAlert(
                variant_id=v.id,
                available=avail,
                reorder_point=int(v.reorder_point),
                missing=missing,
            ))
    return alerts

def compute_replenishment_suggestion(db: Session, supplier_id: uuid.UUID | str | None = None) -> ReplenishmentSuggestion:
    alerts = compute_stock_alerts(db, supplier_id)
    lines: list[ReplenishmentLine] = []

    for a in alerts:
        v = db.get(ProductVariant, a.variant_id)
        # sugerimos el mayor entre el "hueco al mínimo" y el "lote sugerido"
        suggested = max(1, max(a.missing, int(v.reorder_qty or 0)))
        last_cost = _get_last_unit_cost(db, a.variant_id)

        lines.append(ReplenishmentLine(
            variant_id=a.variant_id,
            suggested_qty=suggested,
            reason=f"available({a.available}) <= reorder_point({a.reorder_point})",
            last_unit_cost=last_cost
        ))

    return ReplenishmentSuggestion(
        supplier_id=uuid.UUID(str(supplier_id)) if supplier_id else None,
        lines=sorted(lines, key=lambda L: str(L.variant_id))
    )

def _get_last_unit_cost(db: Session, variant_id: uuid.UUID) -> float | None:
    row = db.execute(
        select(PurchaseOrderLine.unit_cost)
        .where(PurchaseOrderLine.variant_id == variant_id)
        .order_by(PurchaseOrderLine.id.desc())
        .limit(1)
    ).first()
    return float(row[0]) if row else None
