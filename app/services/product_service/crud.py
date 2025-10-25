from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async, rollback_async
from app.models.product import Product, ProductVariant, ProductImage
from app.schemas.product import ProductCreate, ProductUpdate
from .utils import slugify, slug_exists, as_uuid
from app.core.config import settings
from app.services.cloudinary_service import upload_image_from_url


async def create_product(db: AsyncSession, payload: ProductCreate) -> Product:
    base_data = payload.model_dump(exclude={"variants", "images"})
    raw_slug = (base_data.get("slug") or "").strip()
    base_slug = slugify(raw_slug or base_data["title"])
    if await slug_exists(db, base_slug):
        raise HTTPException(status_code=400, detail="Product slug already exists")

    raw_category_id = base_data.pop("category_id", None)
    raw_brand_id    = base_data.pop("brand_id", None)
    category_uuid = as_uuid(raw_category_id, "category_id")
    brand_uuid    = as_uuid(raw_brand_id, "brand_id")

    base_data.pop("slug", None)

    prod = Product(**base_data, slug=base_slug)
    prod.category_id = category_uuid
    prod.brand_id = brand_uuid

    db.add(prod)

    try:
        await flush_async(db, prod)

        for v in payload.variants:
            var = ProductVariant(product_id=prod.id, **v.model_dump())
            db.add(var)

        for i in payload.images:
            image_data = i.model_dump()
            if image_data.get("url") is not None:
                original_url = str(image_data["url"])
                image_data["url"] = original_url
                if not original_url.startswith("https://res.cloudinary.com/"):
                    uploaded_url = await upload_image_from_url(
                        original_url,
                        folder=f"{settings.CLOUDINARY_UPLOAD_FOLDER}/{prod.id}",
                    )
                    if uploaded_url:
                        image_data["url"] = uploaded_url
            img = ProductImage(product_id=prod.id, **image_data)
            db.add(img)

        await flush_async(db)
    except IntegrityError:
        await rollback_async(db)
        raise HTTPException(status_code=400, detail="Unable to create product due to integrity violation")

    await refresh_async(db, prod, attribute_names=["variants", "images", "category", "brand"])
    return prod


async def update_product(db: AsyncSession, prod: Product, changes: ProductUpdate) -> Product:
    data = changes.model_dump(exclude_unset=True)

    if "category_id" in data:
        data["category_id"] = as_uuid(data["category_id"], "category_id")
    if "brand_id" in data:
        data["brand_id"] = as_uuid(data["brand_id"], "brand_id")

    if "slug" in data and data["slug"] is not None:
        new_slug = slugify((data["slug"] or "").strip())
        if new_slug and new_slug != prod.slug and await slug_exists(db, new_slug):
            raise HTTPException(status_code=400, detail="Product slug already exists")
        data["slug"] = new_slug or prod.slug

    for k, v in data.items():
        setattr(prod, k, v)

    db.add(prod)
    try:
        await flush_async(db, prod)
    except IntegrityError:
        await rollback_async(db)
        raise HTTPException(status_code=400, detail="Unable to update product due to integrity violation")
    await refresh_async(db, prod, attribute_names=["variants", "images", "category", "brand"])
    return prod
