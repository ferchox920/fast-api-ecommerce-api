from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models.product import Product, ProductVariant
from app.schemas.variant import VariantCreate, VariantUpdate


def list_variants_for_product(db: Session, product: Product) -> list[ProductVariant]:
    return (
        db.query(ProductVariant)
        .filter(ProductVariant.product_id == product.id)
        .order_by(ProductVariant.size_label, ProductVariant.color_name)
        .all()
    )


def create_variant(db: Session, product: Product, data: VariantCreate) -> ProductVariant:
    # Reglas simples de stock
    if data.stock_reserved and data.stock_reserved > data.stock_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    variant = ProductVariant(
        product_id=product.id,
        sku=data.sku.strip(),
        barcode=(data.barcode.strip() if data.barcode else None),
        size_label=data.size_label.strip(),
        color_name=data.color_name.strip(),
        color_hex=(data.color_hex.strip() if data.color_hex else None),
        stock_on_hand=data.stock_on_hand,
        stock_reserved=data.stock_reserved,
        price_override=data.price_override,
        active=data.active,
    )
    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # SKU único
        raise HTTPException(status_code=400, detail="SKU ya existe")
    db.refresh(variant)
    return variant


def update_variant(db: Session, variant: ProductVariant, changes: VariantUpdate) -> ProductVariant:
    payload = changes.model_dump(exclude_unset=True)

    # Actualizamos campos básicos
    for f in ("barcode", "size_label", "color_name", "color_hex", "price_override", "active"):
        if f in payload:
            setattr(variant, f, payload[f])

    # Stock: si llega uno u otro, validar consistencia
    new_on_hand = payload.get("stock_on_hand", variant.stock_on_hand)
    new_reserved = payload.get("stock_reserved", variant.stock_reserved)

    if new_reserved < 0 or new_on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved > new_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    variant.stock_on_hand = new_on_hand
    variant.stock_reserved = new_reserved

    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Violación de integridad")
    db.refresh(variant)
    return variant


def delete_variant(db: Session, variant: ProductVariant) -> None:
    db.delete(variant)
    db.commit()
