# app/api/routers/purchases.py
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Security,
    status,
    Path,
)
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User

from app.schemas.supplier import SupplierCreate, SupplierRead
from app.schemas.purchase import POCreate, PORead, POLineCreate, POReceivePayload
from app.services import purchase_service

# Reposición
from app.schemas.inventory_replenishment import ReplenishmentSuggestion, StockAlert
from app.services import inventory_service


# Payload para crear PO desde sugerencias
class POCreateFromSuggestionPayload(BaseModel):
    supplier_id: UUID


router = APIRouter(prefix="/purchases", tags=["purchases"])


# ---------- Suppliers (scopes: purchases:write / purchases:read) ----------
@router.post(
    "/suppliers",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    return purchase_service.create_supplier(db, payload)


@router.get(
    "/suppliers",
    response_model=list[SupplierRead],
)
def list_suppliers(
    q: Optional[str] = Query(None, description="Texto de búsqueda"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:read"]),
):
    return purchase_service.list_suppliers(db, q, limit, offset)


# ---------- Purchase Orders (scopes: purchases:write / purchases:read) ----------
@router.post(
    "/orders",
    response_model=PORead,
    status_code=status.HTTP_201_CREATED,
)
def create_po(
    payload: POCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    return purchase_service.create_po(db, payload)


@router.get(
    "/orders/{po_id}",
    response_model=PORead,
)
def get_po(
    po_id: UUID = Path(..., description="ID de la orden de compra"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:read"]),
):
    po = purchase_service.get_po(db, str(po_id))
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    return po


@router.post(
    "/orders/{po_id}/lines",
    response_model=PORead,
)
def add_line(
    po_id: UUID = Path(..., description="ID de la orden de compra"),
    payload: POLineCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    po = purchase_service.get_po(db, str(po_id))
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    return purchase_service.add_line(db, po, payload)


@router.post(
    "/orders/{po_id}/place",
    response_model=PORead,
)
def place_po(
    po_id: UUID = Path(..., description="ID de la orden de compra"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    po = purchase_service.get_po(db, str(po_id))
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    return purchase_service.place_po(db, po)


@router.post(
    "/orders/{po_id}/receive",
    response_model=PORead,
)
def receive_po(
    po_id: UUID = Path(..., description="ID de la orden de compra"),
    payload: POReceivePayload = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    po = purchase_service.get_po(db, str(po_id))
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    return purchase_service.receive_po(db, po, payload)


@router.post(
    "/orders/{po_id}/cancel",
    response_model=PORead,
)
def cancel_po(
    po_id: UUID = Path(..., description="ID de la orden de compra"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    po = purchase_service.get_po(db, str(po_id))
    if not po:
        raise HTTPException(status_code=404, detail="PO not found")
    return purchase_service.cancel_po(db, po)


@router.post(
    "/orders/from-suggestions",
    response_model=PORead,
    status_code=status.HTTP_201_CREATED,
    summary="Create PO from replenishment suggestions",
)
def create_po_from_suggestions_endpoint(
    payload: POCreateFromSuggestionPayload,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:write"]),
):
    """
    Genera automáticamente una orden de compra (en borrador) para un proveedor,
    basándose en las alertas de stock bajo (available <= reorder_point).
    """
    return purchase_service.create_po_from_suggestions(db, str(payload.supplier_id))


# ---------- Replenishment (scope: purchases:read) ----------
@router.get(
    "/replenishment/alerts",
    response_model=list[StockAlert],
)
def replenishment_alerts(
    supplier_id: Optional[UUID] = Query(None, description="Filtra por proveedor"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:read"]),
):
    """
    Devuelve las variantes que cruzaron el umbral (available <= reorder_point).
    """
    return inventory_service.compute_stock_alerts(db, supplier_id)


@router.get(
    "/replenishment/suggestions",
    response_model=ReplenishmentSuggestion,
)
def replenishment_suggestions(
    supplier_id: Optional[UUID] = Query(None, description="Filtra por proveedor"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["purchases:read"]),
):
    """
    Devuelve sugerencias de compra agrupadas por supplier (si se filtra) o globales.
    """
    return inventory_service.compute_replenishment_suggestion(db, supplier_id)
