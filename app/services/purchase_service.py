# app/services/purchase_service.py (fragmentos clave)
from __future__ import annotations
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import uuid

from app.models.supplier import Supplier
from app.models.purchase import PurchaseOrder, PurchaseOrderLine, POStatus
from app.models.product import ProductVariant
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services import inventory_service
from app.services.exceptions import ServiceError
from app.schemas.purchase import POCreate, POLineCreate, POReceivePayload  # <-- tus schemas reales
from sqlalchemy import func, select
from app.services import product_service

def _as_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(422, f"Invalid UUID for {field}")

# ---------- Suppliers ----------
def create_supplier(db: Session, payload: SupplierCreate) -> Supplier:
    if db.query(Supplier).filter(func.lower(Supplier.name) == payload.name.lower()).first():
        raise HTTPException(400, "Supplier name already exists")
    sup = Supplier(**payload.model_dump())
    db.add(sup); db.commit(); db.refresh(sup)
    return sup

def list_suppliers(db: Session, q: str | None = None, limit: int = 50, offset: int = 0) -> list[Supplier]:
    stmt = select(Supplier)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(func.lower(Supplier.name).ilike(func.lower(like)))
    stmt = stmt.order_by(Supplier.name.asc()).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()

def get_supplier(db: Session, supplier_id: str) -> Supplier | None:
    return db.get(Supplier, _as_uuid(supplier_id, "supplier_id"))

# ---------- Purchase Orders ----------
def create_po(db: Session, payload: POCreate) -> PurchaseOrder:
    supplier = get_supplier(db, payload.supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found")

    po = PurchaseOrder(
        supplier_id=supplier.id,
        currency=payload.currency or "ARS",
        status=POStatus.draft,
    )
    db.add(po); db.flush()

    for line in payload.lines:
        _add_line(db, po, line)

    db.commit(); db.refresh(po)
    return po

def _add_line(db: Session, po: PurchaseOrder, line: POLineCreate) -> PurchaseOrderLine:
    variant = db.get(ProductVariant, _as_uuid(line.variant_id, "variant_id"))
    if not variant:
        raise HTTPException(404, "Variant not found")

    pol = PurchaseOrderLine(
        po_id=po.id,
        variant_id=variant.id,
        qty_ordered=line.quantity,   # <-- importantísimo: schema usa 'quantity'
        qty_received=0,
        unit_cost=line.unit_cost,
    )
    db.add(pol)
    return pol

def add_line(db: Session, po: PurchaseOrder, line: POLineCreate) -> PurchaseOrder:
    if po.status != POStatus.draft:
        raise HTTPException(400, "Only draft PO can be modified")
    _add_line(db, po, line)
    db.commit(); db.refresh(po)
    return po

def place_po(db: Session, po: PurchaseOrder) -> PurchaseOrder:
    if po.status != POStatus.draft:
        raise HTTPException(400, "Only draft PO can be placed")
    if not po.lines:
        raise HTTPException(400, "PO needs at least one line")
    po.status = POStatus.placed
    db.add(po); db.commit(); db.refresh(po)
    return po

def receive_po(db: Session, po: PurchaseOrder, payload: POReceivePayload) -> PurchaseOrder:
    if po.status not in [POStatus.placed, POStatus.partially_received, POStatus.draft]:
        raise HTTPException(400, "PO must be placed to receive")

    if not payload.items:
        raise HTTPException(400, "No items to receive")

    line_map = {str(l.id): l for l in po.lines}

    for r in payload.items:  # <-- schema usa 'items'
        line = line_map.get(str(r.line_id))  # <-- schema usa 'line_id'
        if not line:
            raise HTTPException(404, f"Line {r.line_id} not found in PO")

        remaining = line.qty_ordered - line.qty_received
        if r.quantity > remaining:  # <-- schema usa 'quantity'
            raise HTTPException(400, f"Receive qty exceeds remaining (remaining={remaining})")

        # actualizar cantidades
        line.qty_received += r.quantity
        db.add(line)

        # movimiento de inventario
        variant = db.get(ProductVariant, line.variant_id)
        reason = payload.reason or f"PO {po.id}"
        try:
            # Asumimos que product_service.receive_stock llama a inventory_service.receive_stock
            inventory_service.receive_stock(db, variant, r.quantity, reason)
        except ServiceError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # actualizar estado
    total_remaining = sum(l.qty_ordered - l.qty_received for l in po.lines)
    po.status = POStatus.received if total_remaining == 0 else POStatus.partially_received

    db.add(po); db.commit(); db.refresh(po)
    return po

def get_po(db: Session, po_id: str) -> PurchaseOrder | None:
    return db.get(PurchaseOrder, _as_uuid(po_id, "po_id"))

def create_po_from_suggestions(db: Session, supplier_id: str) -> PurchaseOrder:
    """
    Crea una nueva Orden de Compra en estado 'draft' a partir de las
    sugerencias de reposición para un proveedor específico.
    """
    supplier = get_supplier(db, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # 1. Obtener sugerencias de reposición
    suggestions = inventory_service.compute_replenishment_suggestion(db, supplier_id=supplier.id)
    if not suggestions.lines:
        raise HTTPException(status_code=400, detail="No replenishment suggestions found for this supplier")

    # 2. Crear la cabecera de la Orden de Compra
    po = PurchaseOrder(
        supplier_id=supplier.id,
        currency="ARS",  # o la moneda por defecto que prefieras
        status=POStatus.draft,
    )
    db.add(po)
    db.flush()  # Para obtener el po.id antes de crear las líneas

    # 3. Crear las líneas de la orden a partir de las sugerencias
    for line_sugg in suggestions.lines:
        variant = db.get(ProductVariant, line_sugg.variant_id)
        if not variant:
            # Raro que ocurra, pero es una buena validación
            continue

        line_po = PurchaseOrderLine(
            po_id=po.id,
            variant_id=variant.id,
            qty_ordered=line_sugg.suggested_qty,
            # Usamos el último costo o un default de 0 si no existe
            unit_cost=line_sugg.last_unit_cost or 0.0,
        )
        db.add(line_po)

    db.commit()
    db.refresh(po)
    return po