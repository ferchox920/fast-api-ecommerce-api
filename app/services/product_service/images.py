from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.product import Product, ProductImage
from app.schemas.product import ProductImageCreate
from .utils import as_uuid

def add_image(db: Session, product_id: str, data: ProductImageCreate) -> ProductImage:
    pid = as_uuid(product_id, "product_id")

    existing = (
        db.query(ProductImage)
        .filter(ProductImage.product_id == pid)
        .order_by(ProductImage.sort_order.desc())
        .all()
    )
    has_images = len(existing) > 0
    max_sort = existing[0].sort_order if has_images else -1

    payload = data.model_dump()
    if payload.get("url") is not None:
        payload["url"] = str(payload["url"])
    if payload.get("sort_order") is None:
        payload["sort_order"] = max_sort + 1

    img = ProductImage(product_id=pid, **payload)
    db.add(img)
    db.flush()

    make_primary = (not has_images) or bool(payload.get("is_primary"))
    if make_primary:
        db.query(ProductImage).filter(ProductImage.product_id == pid).update({ProductImage.is_primary: False})
        db.query(ProductImage).filter(ProductImage.id == img.id).update({ProductImage.is_primary: True})

    db.commit(); db.refresh(img)
    return img

def set_primary_image(db: Session, product: Product, image_id: str) -> Product:
    img = (
        db.query(ProductImage)
        .filter(
            ProductImage.id == as_uuid(image_id, "image_id"),
            ProductImage.product_id == product.id,
        )
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="Image not found for this product")

    db.query(ProductImage).filter(ProductImage.product_id == product.id).update({ProductImage.is_primary: False})
    db.query(ProductImage).filter(ProductImage.id == img.id).update({ProductImage.is_primary: True})

    db.commit(); db.refresh(product)
    return product
