# app/services/product_service/images.py
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async
from app.models.product import Product, ProductImage
from app.schemas.product import ProductImageCreate
from .utils import as_uuid


async def add_image(db: AsyncSession, product_id: str, data: ProductImageCreate) -> ProductImage:
    pid = as_uuid(product_id, "product_id")

    existing_result = await db.execute(
        select(ProductImage)
        .where(ProductImage.product_id == pid)
        .order_by(ProductImage.sort_order.desc())
    )
    existing = existing_result.scalars().all()
    has_images = len(existing) > 0
    max_sort = existing[0].sort_order if has_images else -1

    payload = data.model_dump()
    if payload.get("url") is not None:
        payload["url"] = str(payload["url"])
    if payload.get("sort_order") is None:
        payload["sort_order"] = max_sort + 1

    image = ProductImage(product_id=pid, **payload)
    db.add(image)
    await flush_async(db, image)

    make_primary = (not has_images) or bool(payload.get("is_primary"))
    if make_primary:
        await db.execute(
            update(ProductImage)
            .where(ProductImage.product_id == pid)
            .values(is_primary=False)
        )
        await db.execute(
            update(ProductImage)
            .where(ProductImage.id == image.id)
            .values(is_primary=True)
        )

    await flush_async(db)
    await refresh_async(db, image)
    return image


async def set_primary_image(db: AsyncSession, product: Product, image_id: str) -> Product:
    image_result = await db.execute(
        select(ProductImage).where(
            ProductImage.id == as_uuid(image_id, "image_id"),
            ProductImage.product_id == product.id,
        )
    )
    image = image_result.scalars().first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found for this product")

    await db.execute(
        update(ProductImage)
        .where(ProductImage.product_id == product.id)
        .values(is_primary=False)
    )
    await db.execute(
        update(ProductImage)
        .where(ProductImage.id == image.id)
        .values(is_primary=True)
    )

    await flush_async(db)
    await refresh_async(db, product, attribute_names=["images"])
    return product
