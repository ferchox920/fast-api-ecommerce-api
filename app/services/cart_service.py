from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.cart import Cart, CartItem, CartStatus
from app.models.product import ProductVariant
from app.schemas.cart import CartCreate, CartItemCreate, CartItemUpdate
from app.services.pricing import get_variant_effective_price


def _as_uuid(value: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(422, f"Invalid UUID for {field}")


def _recompute_totals(cart: Cart) -> None:
    subtotal = sum(float(item.line_total) for item in cart.items)
    cart.subtotal_amount = subtotal
    cart.total_amount = subtotal - float(cart.discount_amount or 0)


def get_active_cart(
    db: Session,
    *,
    user_id: str | None = None,
    guest_token: str | None = None,
) -> Cart | None:
    query = db.query(Cart).filter(Cart.status == CartStatus.active)
    if user_id:
        query = query.filter(Cart.user_id == user_id)
    elif guest_token:
        query = query.filter(Cart.guest_token == guest_token)
    else:
        return None
    return query.order_by(Cart.created_at.desc()).first()


def create_cart(
    db: Session,
    *,
    payload: CartCreate,
    user_id: str | None = None,
) -> Cart:
    guest_token = payload.guest_token

    if not user_id and not guest_token:
        guest_token = str(uuid.uuid4())

    cart = Cart(
        user_id=user_id,
        guest_token=guest_token,
        currency=payload.currency,
        status=CartStatus.active,
        subtotal_amount=0,
        discount_amount=0,
        total_amount=0,
    )
    db.add(cart)
    db.commit(); db.refresh(cart)
    return cart


def _get_item(cart: Cart, item_id: uuid.UUID) -> CartItem | None:
    for item in cart.items:
        if item.id == item_id:
            return item
    return None


def add_item(
    db: Session,
    *,
    cart: Cart,
    item_payload: CartItemCreate,
) -> Cart:
    variant = db.get(ProductVariant, _as_uuid(item_payload.variant_id, "variant_id"))
    if not variant:
        raise HTTPException(404, "Variant not found")

    unit_price = get_variant_effective_price(db, variant)

    existing = next((i for i in cart.items if i.variant_id == variant.id), None)
    if existing:
        existing.quantity += item_payload.quantity
        existing.line_total = float(existing.unit_price) * existing.quantity
    else:
        new_item = CartItem(
            cart=cart,
            variant_id=variant.id,
            quantity=item_payload.quantity,
            unit_price=unit_price,
            line_total=unit_price * item_payload.quantity,
        )
        db.add(new_item)

    _recompute_totals(cart)
    db.add(cart)
    db.commit(); db.refresh(cart)
    return cart


def update_item(
    db: Session,
    *,
    cart: Cart,
    item_id: str,
    payload: CartItemUpdate,
) -> Cart:
    item_uuid = _as_uuid(item_id, "item_id")
    item = _get_item(cart, item_uuid)
    if not item:
        raise HTTPException(404, "Cart item not found")

    item.quantity = payload.quantity
    item.line_total = float(item.unit_price) * item.quantity

    _recompute_totals(cart)
    db.add(cart)
    db.commit(); db.refresh(cart)
    return cart


def remove_item(
    db: Session,
    *,
    cart: Cart,
    item_id: str,
) -> Cart:
    item_uuid = _as_uuid(item_id, "item_id")
    item = _get_item(cart, item_uuid)
    if not item:
        raise HTTPException(404, "Cart item not found")

    cart.items.remove(item)
    db.flush()
    _recompute_totals(cart)

    db.add(cart)
    db.commit(); db.refresh(cart)
    return cart
