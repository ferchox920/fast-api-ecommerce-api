from sqlalchemy.orm import Session
from fastapi import HTTPException
import uuid

from app.models.product import ProductVariant
from app.schemas.product import ProductVariantUpdate

def _as_uuid(v: str) -> uuid.UUID:
    try:
        return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))
    except Exception:
        raise HTTPException(422, "Invalid UUID")

def get_variant(db: Session, variant_id: str | uuid.UUID) -> ProductVariant | None:
    return db.get(ProductVariant, _as_uuid(variant_id))

def update_variant(db: Session, variant_id: str | uuid.UUID, payload: ProductVariantUpdate) -> ProductVariant:
    variant = get_variant(db, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    data = payload.model_dump(exclude_unset=True)
    # Asignación segura de campos permitidos
    for field in [
        "size_label", "color_name", "color_hex",
        "stock_on_hand", "stock_reserved",
        "price_override", "barcode", "active",
        "reorder_point", "reorder_qty", "primary_supplier_id",
    ]:
        if field in data:
            setattr(variant, field, data[field])

    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant
