from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func

from app.models.product import Product, ProductVariant
from .utils import as_uuid

def list_products(
    db: Session,
    q: str | None = None,
    category_id: str | None = None,
    brand_id: str | None = None,
    color: str | None = None,
    size: str | None = None,
    gender: str | None = None,
    fit: str | None = None,
    season: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    skip: int = 0,
    limit: int = 20,
) -> Sequence[Product]:
    stmt = select(Product).where(Product.active == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.description.ilike(like)))
    if category_id:
        stmt = stmt.where(Product.category_id == as_uuid(category_id, "category_id"))
    if brand_id:
        stmt = stmt.where(Product.brand_id == as_uuid(brand_id, "brand_id"))
    if gender:
        stmt = stmt.where(Product.gender == gender)
    if fit:
        stmt = stmt.where(Product.fit == fit)
    if season:
        stmt = stmt.where(Product.season == season)
    if price_min is not None:
        stmt = stmt.where(Product.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Product.price <= price_max)

    if color or size:
        pv = ProductVariant
        v_filters = [pv.active == True]  # noqa: E712
        if color:
            v_filters.append(func.lower(pv.color_name) == func.lower(color))
        if size:
            v_filters.append(func.lower(pv.size_label) == func.lower(size))
        stmt = stmt.join(pv, pv.product_id == Product.id).where(and_(*v_filters)).distinct()

    stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()

def get_product_by_slug(db: Session, slug: str) -> Product | None:
    return db.query(Product).filter(Product.slug == slug, Product.active == True).first()  # noqa: E712

def get_product_by_id(db: Session, product_id: str) -> Product | None:
    return db.get(Product, as_uuid(product_id, "product_id"))

def list_products_with_total(
    db: Session,
    search: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Product], int]:
    from sqlalchemy import func as sa_func  # evitar shadowing
    stmt = select(Product).where(Product.active == True)  # noqa: E712

    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.description.ilike(like)))
    if category:
        stmt = stmt.where(Product.category_id == as_uuid(category, "category"))
    if brand:
        stmt = stmt.where(Product.brand_id == as_uuid(brand, "brand"))
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    base_subq = stmt.order_by(None).subquery()
    total = db.execute(select(sa_func.count()).select_from(base_subq)).scalar_one()

    items = db.execute(
        stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    return items, total
