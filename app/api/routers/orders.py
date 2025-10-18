from typing import List, Optional

from fastapi import APIRouter, Depends, Security, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from uuid import UUID
from pydantic import BaseModel

from app.db.session import get_db
from app.api.deps import get_current_user, get_optional_user
from app.models.user import User
from app.schemas.order import OrderCreate, OrderRead, OrderLineCreate, ShipmentCreate
from app.models.order import OrderStatus, PaymentStatus, ShippingStatus
from app.services import order_service, cart_service


class OrderFromCartPayload(BaseModel):
    guest_token: Optional[str] = None


router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=List[OrderRead])
def list_orders(
    status_filter: Optional[OrderStatus] = Query(default=None, alias="status"),
    payment_status: Optional[PaymentStatus] = Query(default=None),
    shipping_status: Optional[ShippingStatus] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:read"]),
):
    return order_service.list_orders(
        db,
        status_filter=status_filter,
        payment_status=payment_status,
        shipping_status=shipping_status,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    return order_service.create_order(db, current_user_id=current_user.id, payload=payload)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:read"]),
):
    o = order_service.get_order(db, str(order_id))
    if not o:
        raise HTTPException(404, "Order not found")
    return o


@router.post("/from-cart", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order_from_cart(
    payload: OrderFromCartPayload,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    cart = cart_service.get_active_cart(
        db,
        user_id=current_user.id if current_user else None,
        guest_token=payload.guest_token,
    )
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return order_service.create_order_from_cart(db, cart)


@router.post("/{order_id}/lines", response_model=OrderRead)
def add_line(
    order_id: UUID,
    payload: OrderLineCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    o = order_service.get_order(db, str(order_id))
    if not o:
        raise HTTPException(404, "Order not found")
    return order_service.add_line(db, o, payload)


@router.post("/{order_id}/pay", response_model=OrderRead)
def pay_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    o = order_service.get_order(db, str(order_id))
    if not o:
        raise HTTPException(404, "Order not found")
    return order_service.set_status_paid(db, o)


@router.post("/{order_id}/cancel", response_model=OrderRead)
def cancel_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    o = order_service.get_order(db, str(order_id))
    if not o:
        raise HTTPException(404, "Order not found")
    return order_service.cancel_order(db, o)


@router.post("/{order_id}/fulfill", response_model=OrderRead)
def fulfill_order(
    order_id: UUID,
    payload: Optional[ShipmentCreate] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    o = order_service.get_order(db, str(order_id))
    if not o:
        raise HTTPException(404, "Order not found")
    return order_service.fulfill_order(db, o, payload)
