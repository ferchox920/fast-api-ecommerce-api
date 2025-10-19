from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductVariant


async def get_variant_effective_price(db: AsyncSession, variant: ProductVariant) -> float:
    """Return the price applicable for carts/orders using AsyncSession."""
    if variant.price_override is not None:
        return float(variant.price_override)

    product = await db.get(Product, variant.product_id)
    if not product:
        raise HTTPException(500, "Variant without product")

    return float(product.price)
