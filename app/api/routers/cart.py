from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_optional_user
from app.models.user import User
from app.schemas.cart import (
    CartCreate,
    CartItemCreate,
    CartItemUpdate,
    CartRead,
)
from app.services import cart_service


router = APIRouter(prefix="/cart", tags=["cart"])


def _resolve_context(current_user: User | None, guest_token: str | None) -> tuple[str | None, str | None]:
    if current_user:
        return current_user.id, None
    if guest_token:
        return None, guest_token
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "guest_token is required for anonymous carts")


@router.post("", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def create_or_get_cart(
    payload: CartCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    if current_user:
        existing = cart_service.get_active_cart(db, user_id=current_user.id)
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing
        return cart_service.create_cart(db, payload=payload, user_id=current_user.id)

    # guest cart
    existing = cart_service.get_active_cart(db, guest_token=payload.guest_token)
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing
    return cart_service.create_cart(db, payload=payload, user_id=None)


@router.get("", response_model=CartRead)
def get_cart(
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return cart


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    item: CartItemCreate,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)

    cart = cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        # crear automáticamente el carrito para simplificar flujos
        cart_payload = CartCreate(guest_token=token, currency="ARS")
        cart = cart_service.create_cart(db, payload=cart_payload, user_id=user_id)
    return cart_service.add_item(db, cart=cart, item_payload=item)


@router.put("/items/{item_id}", response_model=CartRead)
def update_cart_item(
    item_id: str,
    payload: CartItemUpdate,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return cart_service.update_item(db, cart=cart, item_id=item_id, payload=payload)


@router.delete("/items/{item_id}", response_model=CartRead)
def remove_cart_item(
    item_id: str,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return cart_service.remove_item(db, cart=cart, item_id=item_id)
