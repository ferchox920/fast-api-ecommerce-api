from __future__ import annotations
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.product import ProductVariant, Product


def get_variant_effective_price(db: Session, variant: ProductVariant) -> float:
    """Devuelve el precio aplicable para ventas/carrito.

    Prioriza `price_override` de la variante y cae al precio base del producto.
    """

    if variant.price_override is not None:
        return float(variant.price_override)

    product = db.get(Product, variant.product_id)
    if not product:
        raise HTTPException(500, "Variant without product")

    return float(product.price)
