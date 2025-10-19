# app/services/product_service/variants.py
from typing import Union

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async, rollback_async
from app.models.product import Product, ProductVariant
from app.schemas.product import ProductVariantCreate, ProductVariantUpdate
from app.schemas.variant import VariantCreate, VariantUpdate
from .utils import as_uuid


async def list_variants_for_product(db: AsyncSession, product: Product) -> list[ProductVariant]:
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product.id)
        .order_by(ProductVariant.size_label, ProductVariant.color_name)
    )
    return result.scalars().all()


async def add_variant(
    db: AsyncSession,
    product_id: str,
    data: Union[ProductVariantCreate, VariantCreate],
) -> ProductVariant:
    if isinstance(data, VariantCreate):
        payload_data = data.model_dump()
        data = ProductVariantCreate(**payload_data)

    if (
        data.stock_reserved is not None
        and data.stock_on_hand is not None
        and data.stock_reserved > data.stock_on_hand
    ):
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    payload = data.model_dump()
    payload["sku"] = payload["sku"].strip()
    if payload.get("barcode"):
        payload["barcode"] = payload["barcode"].strip()
    payload["size_label"] = payload["size_label"].strip()
    payload["color_name"] = payload["color_name"].strip()
    if payload.get("color_hex"):
        payload["color_hex"] = payload["color_hex"].strip()

    variant = ProductVariant(product_id=as_uuid(product_id, "product_id"), **payload)
    db.add(variant)
    try:
        await flush_async(db, variant)
    except IntegrityError:
        await rollback_async(db)
        raise HTTPException(status_code=400, detail="SKU ya existe")

    await refresh_async(db, variant)
    return variant


async def update_variant(
    db: AsyncSession,
    variant: ProductVariant,
    changes: Union[ProductVariantUpdate, VariantUpdate],
) -> ProductVariant:
    if isinstance(changes, VariantUpdate):
        changes = ProductVariantUpdate(**changes.model_dump(exclude_unset=True))

    payload = changes.model_dump(exclude_unset=True)

    new_on_hand = payload.get("stock_on_hand", variant.stock_on_hand)
    new_reserved = payload.get("stock_reserved", variant.stock_reserved)

    if new_on_hand is not None and new_on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved is not None and new_reserved < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved > new_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    for field, value in payload.items():
        setattr(variant, field, value)

    db.add(variant)
    try:
        await flush_async(db, variant)
    except IntegrityError:
        await rollback_async(db)
        raise HTTPException(status_code=400, detail="Violacion de integridad")

    await refresh_async(db, variant)
    return variant


async def get_variant(db: AsyncSession, variant_id: str) -> ProductVariant | None:
    return await db.get(ProductVariant, as_uuid(variant_id, "variant_id"))


async def delete_variant(db: AsyncSession, variant: ProductVariant) -> None:
    await db.delete(variant)
    await flush_async(db)


async def set_stock(
    db: AsyncSession,
    variant: ProductVariant,
    on_hand: int | None = None,
    reserved: int | None = None,
) -> ProductVariant:
    if on_hand is not None:
        if on_hand < 0:
            raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
        variant.stock_on_hand = on_hand
    if reserved is not None:
        if reserved < 0:
            raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
        if reserved > (variant.stock_on_hand if on_hand is None else on_hand):
            raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")
        variant.stock_reserved = reserved

    db.add(variant)
    await flush_async(db, variant)
    await refresh_async(db, variant)
    return variant


async def create_variant(db: AsyncSession, product: Product, data: VariantCreate) -> ProductVariant:
    return await add_variant(db, str(product.id), data)
