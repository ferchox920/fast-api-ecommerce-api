# app/services/product_service/inventory.py
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from fastapi import HTTPException
from datetime import datetime, timezone, UTC  # ya está importado
import uuid

from app.models.product import ProductVariant

# Clave para no repetir el ensure por sesión/bind
_MOVEMENTS_READY_KEY = "inventory_movements_ready"


def _ensure_movements_table(db: Session) -> None:
    """
    Garantiza que exista 'inventory_movements' una sola vez por bind/sesión.
    - En SQLite: crea la tabla con tipos TEXT/INTEGER (sin migraciones).
    - En otros motores: intenta con el modelo; si falla, hace un CREATE defensivo.
    """
    if db.info.get(_MOVEMENTS_READY_KEY):
        return

    bind = db.get_bind()
    dialect = getattr(bind.dialect, "name", "unknown")

    if dialect == "sqlite":
        # SQLite: tipos textuales para máxima compatibilidad
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id TEXT PRIMARY KEY,
                variant_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                reason VARCHAR(255),
                created_at TIMESTAMP NOT NULL
            )
        """))
        db.info[_MOVEMENTS_READY_KEY] = True
        return

    # Otros motores (e.g., Postgres, MySQL)
    insp = inspect(bind)
    if not insp.has_table("inventory_movements"):
        try:
            # Si existe el modelo declarativo, úsalo
            from app.models.inventory import InventoryMovement
            InventoryMovement.__table__.create(bind=bind, checkfirst=True)
        except Exception:
            # Fallback defensivo
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS inventory_movements (
                    id UUID PRIMARY KEY,
                    variant_id UUID NOT NULL,
                    quantity INTEGER NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    reason VARCHAR(255),
                    created_at TIMESTAMP NOT NULL
                )
            """))

    db.info[_MOVEMENTS_READY_KEY] = True


def _log_movement(db: Session, variant: ProductVariant, mtype: str, qty: int, reason: str | None) -> None:
    _ensure_movements_table(db)
    db.execute(
        text("""
            INSERT INTO inventory_movements (id, variant_id, quantity, type, reason, created_at)
            VALUES (:id, :variant_id, :quantity, :type, :reason, :created_at)
        """),
        {
            "id": str(uuid.uuid4()),
            "variant_id": str(variant.id),
            "quantity": int(qty),
            "type": mtype,
            "reason": reason,
            # ✅ UTC aware -> ISO string (lex-ordenable y sin adapter de sqlite)
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )


def _commit_with_movement(
    db: Session,
    variant: ProductVariant,
    mtype: str,
    qty: int,
    reason: str | None,
) -> ProductVariant:
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
    return _commit_with_movement(db, variant, "adjust", abs(quantity), reason)


def _now_utc():
    return datetime.now(timezone.utc)


def reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    """
    Reserva stock:
    - Si hay disponible (on_hand - reserved) suficiente, reserva normal.
    - Si NO hay disponible:
        - allow_backorder => permite reservar (backorder)
        - allow_preorder y (sin release_at o ahora < release_at) => permite reservar (preorder)
        - en otro caso => 400
    """
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")

    available = variant.stock_on_hand - variant.stock_reserved
    if quantity <= available:
        variant.stock_reserved += quantity
        db.add(variant)
        return _commit_with_movement(db, variant, "reserve", quantity, reason)
    else:
        now = _now_utc()
        if getattr(variant, "allow_backorder", False):
            variant.stock_reserved += quantity
            db.add(variant)
            return _commit_with_movement(db, variant, "reserve", quantity, reason or "backorder")
        if getattr(variant, "allow_preorder", False) and (
            variant.release_at is None or now < variant.release_at
        ):
            variant.stock_reserved += quantity
            db.add(variant)
            return _commit_with_movement(db, variant, "reserve", quantity, reason or "preorder")

        raise HTTPException(status_code=400, detail="Stock insuficiente para reservar")


def release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if quantity > variant.stock_reserved:
        raise HTTPException(status_code=400, detail="No hay reservado suficiente")
    variant.stock_reserved -= quantity
    db.add(variant)
    return _commit_with_movement(db, variant, "release", quantity, reason)


def commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    """
    Concreta venta:
    - Debe haber al menos 'quantity' reservado (venta desde reservas).
    - Si es preorder y aún no llegó release_at => 400.
    - Disminuye reserved y on_hand; si queda on_hand < 0 y no hay allow_backorder => 400 (se revierte reserved).
    """
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if quantity > variant.stock_reserved:
        raise HTTPException(status_code=400, detail="No hay suficiente reservado para concretar la venta")

    now = _now_utc()
    if getattr(variant, "allow_preorder", False) and variant.release_at and now < variant.release_at:
        raise HTTPException(status_code=400, detail="Aún no liberado para venta (preorder)")

    # Aplico la venta
    variant.stock_reserved -= quantity
    new_on_hand = variant.stock_on_hand - quantity

    if new_on_hand < 0 and not getattr(variant, "allow_backorder", False):
        # Revierto la resta de reserved para no dejar estado inconsistente
        variant.stock_reserved += quantity
        raise HTTPException(status_code=400, detail="Stock físico insuficiente para concretar la venta")

    variant.stock_on_hand = new_on_hand
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
            "created_at": str(r["created_at"]),  # <-- devolver como string para el schema
        }
        for r in rows
    ]
