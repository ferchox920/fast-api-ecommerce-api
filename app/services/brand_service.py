from __future__ import annotations

import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async, rollback_async
from app.models.product import Brand
from app.schemas.brand import BrandCreate, BrandUpdate


async def create_brand(db: AsyncSession, payload: BrandCreate) -> Brand:
    slug = payload.slug or slugify(payload.name)

    exists_stmt = (
        select(Brand.id)
        .where(or_(Brand.name == payload.name, Brand.slug == slug))
        .limit(1)
    )
    exists_result = await db.execute(exists_stmt)
    if exists_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        )

    brand = Brand(
        id=uuid.uuid4(),
        name=payload.name,
        slug=slug,
        description=payload.description,
        active=payload.active,
    )
    db.add(brand)
    try:
        await flush_async(db, brand)
    except IntegrityError as exc:
        await rollback_async(db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        ) from exc
    await refresh_async(db, brand)
    return brand


async def list_all_brands(db: AsyncSession) -> list[Brand]:
    stmt = select(Brand).order_by(Brand.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def list_active_brands(db: AsyncSession) -> list[Brand]:
    stmt = (
        select(Brand)
        .where(Brand.active.is_(True))
        .order_by(Brand.name.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_brand(db: AsyncSession, brand_id: uuid.UUID) -> Brand | None:
    return await db.get(Brand, brand_id)


async def update_brand(db: AsyncSession, brand: Brand, changes: BrandUpdate) -> Brand:
    data = changes.model_dump(exclude_unset=True)

    if "name" in data and data["name"]:
        data.setdefault("slug", slugify(data["name"]))
    if "slug" in data and data["slug"]:
        candidate_slug = slugify(data["slug"])
        if candidate_slug != brand.slug:
            exists_stmt = select(Brand.id).where(Brand.slug == candidate_slug).limit(1)
            exists = await db.execute(exists_stmt)
            if exists.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Brand with the same name or slug already exists",
                )
        data["slug"] = candidate_slug

    for key, value in data.items():
        setattr(brand, key, value)

    try:
        await flush_async(db, brand)
    except IntegrityError as exc:
        await rollback_async(db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        ) from exc
    await refresh_async(db, brand)
    return brand


async def delete_brand(db: AsyncSession, brand: Brand) -> None:
    await db.delete(brand)


# Helper local por si no tenés utilidades aún
def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s[:140]
