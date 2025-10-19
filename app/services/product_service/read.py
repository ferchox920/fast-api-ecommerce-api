from typing import Sequence
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import Product, ProductVariant
from .utils import as_uuid

EAGER_PRODUCT_LOAD = (
    selectinload(Product.category),
    selectinload(Product.brand),
    selectinload(Product.variants),
    selectinload(Product.images),
)


async def list_products(
    db: AsyncSession,
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
    stmt = select(Product).options(*EAGER_PRODUCT_LOAD).where(Product.active == True)  # noqa: E712

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
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_product_by_slug(db: AsyncSession, slug: str) -> Product | None:
    result = await db.execute(
        select(Product)
        .options(*EAGER_PRODUCT_LOAD)
        .where(Product.slug == slug, Product.active == True)  # noqa: E712
    )
    return result.scalars().first()


async def get_product_by_id(db: AsyncSession, product_id: str) -> Product | None:
    return await db.get(
        Product,
        as_uuid(product_id, "product_id"),
        options=EAGER_PRODUCT_LOAD,
    )


async def list_products_with_total(
    db: AsyncSession,
    search: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Product], int]:
    from sqlalchemy import func as sa_func  # evitar shadowing
    stmt = select(Product).options(*EAGER_PRODUCT_LOAD).where(Product.active == True)  # noqa: E712

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
    total_result = await db.execute(select(sa_func.count()).select_from(base_subq))
    total = total_result.scalar_one()

    items_result = await db.execute(
        stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    )
    items = items_result.scalars().all()

    return items, total
