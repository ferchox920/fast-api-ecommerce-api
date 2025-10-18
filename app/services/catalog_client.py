from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from uuid import UUID as UUIDType


def get_financial_metrics(db: Session, product_id) -> dict:
    """Return margin and stock information for a product.

    # INTEGRATION: stock y margen vienen del catálogo/ERP ? agregar adapter 'catalog_client'.
    """
    product_uuid = UUIDType(str(product_id))
    product: Optional[Product] = db.get(Product, product_uuid)
    if not product:
        return {"margin": Decimal("0"), "stock_on_hand": 0, "category_id": None}

    # Placeholder values; replace with real ERP/catalog integration.
    return {
        "margin": Decimal(str(getattr(product, "price", 0))) * Decimal("0.35"),
        "stock_on_hand": 10,
        "category_id": getattr(product, "category_id", None),
    }

