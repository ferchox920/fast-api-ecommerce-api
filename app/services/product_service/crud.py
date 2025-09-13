from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.product import Product, ProductVariant, ProductImage
from app.schemas.product import ProductCreate, ProductUpdate
from .utils import slugify, slug_exists, as_uuid

def create_product(db: Session, payload: ProductCreate) -> Product:
    base_data = payload.model_dump(exclude={"variants", "images"})
    raw_slug = (base_data.get("slug") or "").strip()
    base_slug = slugify(raw_slug or base_data["title"])
    if slug_exists(db, base_slug):
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
    db.flush()

    for v in payload.variants:
        var = ProductVariant(product_id=prod.id, **v.model_dump())
        db.add(var)

    for i in payload.images:
        img = ProductImage(product_id=prod.id, **i.model_dump())
        db.add(img)

    db.commit(); db.refresh(prod)
    return prod

def update_product(db: Session, prod: Product, changes: ProductUpdate) -> Product:
    data = changes.model_dump(exclude_unset=True)

    if "category_id" in data:
        data["category_id"] = as_uuid(data["category_id"], "category_id")
    if "brand_id" in data:
        data["brand_id"] = as_uuid(data["brand_id"], "brand_id")

    if "slug" in data and data["slug"] is not None:
        new_slug = slugify((data["slug"] or "").strip())
        if new_slug and new_slug != prod.slug and slug_exists(db, new_slug):
            raise HTTPException(status_code=400, detail="Product slug already exists")
        data["slug"] = new_slug or prod.slug

    for k, v in data.items():
        setattr(prod, k, v)

    db.add(prod); db.commit(); db.refresh(prod)
    return prod
