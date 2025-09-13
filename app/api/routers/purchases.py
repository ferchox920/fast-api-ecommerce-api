# app/api/routers/purchases.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate

from app.schemas.purchase import (
    POCreate, PORead, POLineCreate, POReceivePayload
)
from app.services import purchase_service

router = APIRouter(prefix="/purchases", tags=["purchases"])

# ---------- Suppliers ----------
@router.post(
    "/suppliers",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    return purchase_service.create_supplier(db, payload)

@router.get(
    "/suppliers",
    response_model=list[SupplierRead],
    dependencies=[Depends(get_current_admin)],
)
def list_suppliers(
    q: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return purchase_service.list_suppliers(db, q, limit, offset)

# (Si más adelante agregas SupplierUpdate, aquí puedes reponer el endpoint de update)

# ---------- Purchase Orders ----------
@router.post(
    "/orders",
    response_model=PORead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create_po(payload: POCreate, db: Session = Depends(get_db)):
    return purchase_service.create_po(db, payload)

@router.get(
    "/orders/{po_id}",
    response_model=PORead,
    dependencies=[Depends(get_current_admin)],
)
def get_po(po_id: str, db: Session = Depends(get_db)):
    po = purchase_service.get_po(db, po_id)
    if not po:
        raise HTTPException(404, "PO not found")
    return po

@router.post(
    "/orders/{po_id}/lines",
    response_model=PORead,
    dependencies=[Depends(get_current_admin)],
)
def add_line(po_id: str, payload: POLineCreate, db: Session = Depends(get_db)):
    po = purchase_service.get_po(db, po_id)
    if not po:
        raise HTTPException(404, "PO not found")
    return purchase_service.add_line(db, po, payload)

@router.post(
    "/orders/{po_id}/place",
    response_model=PORead,
    dependencies=[Depends(get_current_admin)],
)
def place_po(po_id: str, db: Session = Depends(get_db)):
    po = purchase_service.get_po(db, po_id)
    if not po:
        raise HTTPException(404, "PO not found")
    return purchase_service.place_po(db, po)

@router.post(
    "/orders/{po_id}/receive",
    response_model=PORead,
    dependencies=[Depends(get_current_admin)],
)
def receive_po(po_id: str, payload: POReceivePayload, db: Session = Depends(get_db)):
    po = purchase_service.get_po(db, po_id)
    if not po:
        raise HTTPException(404, "PO not found")
    return purchase_service.receive_po(db, po, payload)

@router.post(
    "/orders/{po_id}/cancel",
    response_model=PORead,
    dependencies=[Depends(get_current_admin)],
)
def cancel_po(po_id: str, db: Session = Depends(get_db)):
    po = purchase_service.get_po(db, po_id)
    if not po:
        raise HTTPException(404, "PO not found")
    return purchase_service.cancel_po(db, po)
