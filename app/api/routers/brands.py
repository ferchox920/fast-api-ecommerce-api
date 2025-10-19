from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.models.product import Brand
from app.schemas.brand import BrandCreate, BrandRead, BrandUpdate
from app.services import brand_service

router = APIRouter(prefix="/brands", tags=["brands"])


# --- Público (paginado) ---
@router.get("", summary="List active brands (public)")
async def public_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    filters = Brand.active.is_(True)
    total_stmt = select(func.count()).select_from(Brand).where(filters)
    total = await db.scalar(total_stmt)

    items_stmt = (
        select(Brand)
        .where(filters)
        .order_by(Brand.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items_result = await db.execute(items_stmt)
    items = items_result.scalars().all()

    return {
        "items": [BrandRead.model_validate(b) for b in items],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


# --- Admin ---
@router.get(
    "/all",
    response_model=list[BrandRead],
    dependencies=[Depends(get_current_admin)],
)
async def admin_list(db: AsyncSession = Depends(get_async_db)):
    brands = await brand_service.list_all_brands(db)
    return [BrandRead.model_validate(b) for b in brands]


@router.post(
    "",
    response_model=BrandRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
async def admin_create(payload: BrandCreate, db: AsyncSession = Depends(get_async_db)):
    brand = await brand_service.create_brand(db, payload)
    await commit_async(db)
    return brand


@router.put(
    "/{brand_id}",
    response_model=BrandRead,
    dependencies=[Depends(get_current_admin)],
)
async def admin_update(
    brand_id: str = Path(...),
    payload: BrandUpdate = ...,
    db: AsyncSession = Depends(get_async_db),
):
    try:
        brand_uuid = uuid.UUID(str(brand_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid brand id") from exc

    brand = await brand_service.get_brand(db, brand_uuid)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    updated = await brand_service.update_brand(db, brand, payload)
    await commit_async(db)
    return updated
