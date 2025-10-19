from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user
from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.cart import CartCreate, CartItemCreate, CartItemUpdate, CartRead
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


def _resolve_context(current_user: User | None, guest_token: str | None) -> tuple[str | None, str | None]:
    if current_user:
        return current_user.id, None
    if guest_token:
        return None, guest_token
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "guest_token is required for anonymous carts")


@router.post("", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def create_or_get_cart(
    payload: CartCreate,
    response: Response,
    db: AsyncSession = Depends(get_async_db),
    current_user: User | None = Depends(get_optional_user),
):
    if current_user:
        existing = await cart_service.get_active_cart(db, user_id=current_user.id)
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing
        cart = await cart_service.create_cart(db, payload=payload, user_id=current_user.id)
        await commit_async(db)
        return cart

    existing = await cart_service.get_active_cart(db, guest_token=payload.guest_token)
    if existing:
        response.status_code = status.HTTP_200_OK
        return existing
    cart = await cart_service.create_cart(db, payload=payload, user_id=None)
    await commit_async(db)
    return cart


@router.get("", response_model=CartRead)
async def get_cart(
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = await cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    return cart


@router.post("/items", response_model=CartRead, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    item: CartItemCreate,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)

    cart = await cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        cart_payload = CartCreate(guest_token=token, currency="ARS")
        cart = await cart_service.create_cart(db, payload=cart_payload, user_id=user_id)
        await commit_async(db)
    updated = await cart_service.add_item(db, cart=cart, item_payload=item)
    await commit_async(db)
    return updated


@router.put("/items/{item_id}", response_model=CartRead)
async def update_cart_item(
    item_id: str,
    payload: CartItemUpdate,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = await cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    updated = await cart_service.update_item(db, cart=cart, item_id=item_id, payload=payload)
    await commit_async(db)
    return updated


@router.delete("/items/{item_id}", response_model=CartRead)
async def remove_cart_item(
    item_id: str,
    guest_token: str | None = Query(default=None, description="Token del carrito invitado"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User | None = Depends(get_optional_user),
):
    user_id, token = _resolve_context(current_user, guest_token)
    cart = await cart_service.get_active_cart(db, user_id=user_id, guest_token=token)
    if not cart:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found")
    updated = await cart_service.remove_item(db, cart=cart, item_id=item_id)
    await commit_async(db)
    return updated
