# app/services/purchase_service.py
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async
from app.models.product import ProductVariant
from app.models.purchase import POStatus, PurchaseOrder, PurchaseOrderLine
from app.models.supplier import Supplier
from app.schemas.purchase import POCreate, POLineCreate, POReceivePayload
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services import inventory_service
from app.services.exceptions import (
    ConflictError,
    DomainValidationError,
    ResourceNotFoundError,
    ServiceError,
)


def _as_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception as exc:
        raise DomainValidationError(f"Invalid UUID for {field}") from exc


# ---------- Suppliers ----------
async def create_supplier(db: AsyncSession, payload: SupplierCreate) -> Supplier:
    stmt = select(Supplier).where(func.lower(Supplier.name) == payload.name.lower())
    existing = (await db.execute(stmt)).scalars().first()
    if existing:
        raise ConflictError("Supplier name already exists")

    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    await flush_async(db, supplier)
    await refresh_async(db, supplier)
    return supplier


async def list_suppliers(
    db: AsyncSession,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Supplier]:
    stmt = select(Supplier)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(func.lower(Supplier.name).ilike(func.lower(like)))
    stmt = stmt.order_by(Supplier.name.asc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_supplier(db: AsyncSession, supplier_id: str) -> Supplier | None:
    return await db.get(Supplier, _as_uuid(supplier_id, "supplier_id"))


async def update_supplier(db: AsyncSession, supplier: Supplier, payload: SupplierUpdate) -> Supplier:
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        name = data["name"]
        stmt = (
            select(Supplier)
            .where(func.lower(Supplier.name) == name.lower())
            .where(Supplier.id != supplier.id)
        )
        exists = (await db.execute(stmt)).scalars().first()
        if exists:
            raise ConflictError("Supplier name already exists")

    for field, value in data.items():
        setattr(supplier, field, value)
    db.add(supplier)
    await flush_async(db, supplier)
    await refresh_async(db, supplier)
    return supplier


async def _get_supplier_or_raise(db: AsyncSession, supplier_id: str) -> Supplier:
    supplier = await get_supplier(db, supplier_id)
    if not supplier:
        raise ResourceNotFoundError("Supplier not found")
    return supplier


# ---------- Purchase Orders ----------
async def create_po(db: AsyncSession, payload: POCreate) -> PurchaseOrder:
    await _get_supplier_or_raise(db, payload.supplier_id)

    po = PurchaseOrder(
        supplier_id=_as_uuid(payload.supplier_id, "supplier_id"),
        currency=payload.currency or "ARS",
        status=POStatus.draft,
    )
    db.add(po)
    await flush_async(db, po)

    for line in payload.lines:
        await _add_line(db, po, line)

    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def _add_line(db: AsyncSession, po: PurchaseOrder, line: POLineCreate) -> PurchaseOrderLine:
    variant = await db.get(ProductVariant, _as_uuid(line.variant_id, "variant_id"))
    if not variant:
        raise ResourceNotFoundError("Variant not found")

    pol = PurchaseOrderLine(
        po_id=po.id,
        variant_id=variant.id,
        qty_ordered=line.quantity,
        qty_received=0,
        unit_cost=line.unit_cost,
    )
    db.add(pol)
    await flush_async(db, pol)
    return pol


async def add_line(db: AsyncSession, po: PurchaseOrder, line: POLineCreate) -> PurchaseOrder:
    if po.status != POStatus.draft:
        raise ConflictError("Only draft PO can be modified")
    await _add_line(db, po, line)
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def place_po(db: AsyncSession, po: PurchaseOrder) -> PurchaseOrder:
    if po.status != POStatus.draft:
        raise ConflictError("Only draft PO can be placed")
    await refresh_async(db, po, attribute_names=["lines"])
    if not po.lines:
        raise DomainValidationError("PO needs at least one line")
    po.status = POStatus.placed
    db.add(po)
    await flush_async(db, po)
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def receive_po(db: AsyncSession, po: PurchaseOrder, payload: POReceivePayload) -> PurchaseOrder:
    if po.status not in [POStatus.placed, POStatus.partially_received, POStatus.draft]:
        raise ConflictError("PO must be placed to receive")
    if not payload.items:
        raise DomainValidationError("No items to receive")

    await refresh_async(db, po, attribute_names=["lines"])
    line_map = {str(line.id): line for line in po.lines}

    for item in payload.items:
        line = line_map.get(str(item.line_id))
        if not line:
            raise ResourceNotFoundError(f"Line {item.line_id} not found in PO")

        remaining = line.qty_ordered - line.qty_received
        if item.quantity > remaining:
            raise DomainValidationError(f"Receive quantity exceeds remaining ({remaining})")

        line.qty_received += item.quantity
        db.add(line)
        await flush_async(db, line)

        reason = payload.reason or f"PO {po.id}"

        def _run_receive(sync_db):
            variant_sync = sync_db.get(ProductVariant, line.variant_id)
            if not variant_sync:
                raise ResourceNotFoundError("Variant not found")
            try:
                inventory_service.receive_stock(sync_db, variant_sync, item.quantity, reason)
            except ServiceError as exc:
                raise ConflictError(str(exc))

        await db.run_sync(_run_receive)

    total_remaining = sum(line.qty_ordered - line.qty_received for line in po.lines)
    po.status = POStatus.received if total_remaining == 0 else POStatus.partially_received
    db.add(po)
    await flush_async(db, po)
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def cancel_po(db: AsyncSession, po: PurchaseOrder) -> PurchaseOrder:
    if po.status == POStatus.cancelled:
        raise ConflictError("PO already cancelled")
    if po.status == POStatus.received:
        raise ConflictError("Received PO cannot be cancelled")
    po.status = POStatus.cancelled
    db.add(po)
    await flush_async(db, po)
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def get_po(db: AsyncSession, po_id: str) -> PurchaseOrder:
    po = await db.get(PurchaseOrder, _as_uuid(po_id, "po_id"))
    if not po:
        raise ResourceNotFoundError("PO not found")
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po


async def create_po_from_suggestions(db: AsyncSession, supplier_id: str) -> PurchaseOrder:
    supplier = await _get_supplier_or_raise(db, supplier_id)

    suggestions = await db.run_sync(
        lambda sync_db: inventory_service.compute_replenishment_suggestion(sync_db, supplier_id=supplier.id)
    )
    if not suggestions.lines:
        raise ConflictError("No replenishment suggestions found for this supplier")

    po = PurchaseOrder(
        supplier_id=supplier.id,
        currency="ARS",
        status=POStatus.draft,
    )
    db.add(po)
    await flush_async(db, po)

    for line_sugg in suggestions.lines:
        variant = await db.get(ProductVariant, line_sugg.variant_id)
        if not variant:
            continue
        line_po = PurchaseOrderLine(
            po_id=po.id,
            variant_id=variant.id,
            qty_ordered=line_sugg.suggested_qty,
            unit_cost=line_sugg.last_unit_cost or 0.0,
        )
        db.add(line_po)

    await flush_async(db)
    await refresh_async(db, po)
    await refresh_async(db, po, attribute_names=["lines"])
    return po
