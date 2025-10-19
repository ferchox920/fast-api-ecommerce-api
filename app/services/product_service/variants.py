from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.product import ProductVariant, Product
from app.schemas.product import ProductVariantCreate, ProductVariantUpdate
from .utils import as_uuid


def list_variants_for_product(db: Session, product: Product) -> list[ProductVariant]:
    return (
        db.query(ProductVariant)
        .filter(ProductVariant.product_id == product.id)
        .order_by(ProductVariant.size_label, ProductVariant.color_name)
        .all()
    )

def add_variant(db: Session, product_id: str, data: ProductVariantCreate) -> ProductVariant:
    if (
        data.stock_reserved is not None
        and data.stock_on_hand is not None
        and data.stock_reserved > data.stock_on_hand
    ):
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    payload = data.model_dump()
    payload["sku"] = payload["sku"].strip()
    if payload.get("barcode"): payload["barcode"] = payload["barcode"].strip()
    payload["size_label"] = payload["size_label"].strip()
    payload["color_name"] = payload["color_name"].strip()
    if payload.get("color_hex"): payload["color_hex"] = payload["color_hex"].strip()

    var = ProductVariant(product_id=as_uuid(product_id, "product_id"), **payload)
    db.add(var)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="SKU ya existe")
    db.refresh(var)
    return var

def update_variant(db: Session, variant: ProductVariant, changes: ProductVariantUpdate) -> ProductVariant:
    payload = changes.model_dump(exclude_unset=True)

    new_on_hand = payload.get("stock_on_hand", variant.stock_on_hand)
    new_reserved = payload.get("stock_reserved", variant.stock_reserved)

    if new_on_hand is not None and new_on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved is not None and new_reserved < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved > new_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    for f, v in payload.items():
        setattr(variant, f, v)

    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Violación de integridad")
    db.refresh(variant)
    return variant

def get_variant(db: Session, variant_id: str) -> ProductVariant | None:
    return db.get(ProductVariant, as_uuid(variant_id, "variant_id"))

def delete_variant(db: Session, variant: ProductVariant) -> None:
    db.delete(variant); db.commit()

def set_stock(db: Session, variant: ProductVariant, on_hand: int | None = None, reserved: int | None = None) -> ProductVariant:
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
    db.add(variant); db.commit(); db.refresh(variant)
    return variant
