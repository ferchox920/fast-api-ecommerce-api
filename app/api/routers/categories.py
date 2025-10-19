from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


# --- Público ---
@router.get("", response_model=list[CategoryRead])
async def public_list(db: AsyncSession = Depends(get_async_db)):
    return await category_service.list_active_categories(db)


# --- Admin ---
@router.get(
    "/all",
    response_model=list[CategoryRead],
    dependencies=[Depends(get_current_admin)],
)
async def admin_list(db: AsyncSession = Depends(get_async_db)):
    return await category_service.list_all_categories(db)


@router.post(
    "",
    response_model=CategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
async def admin_create(
    payload: CategoryCreate,
    db: AsyncSession = Depends(get_async_db),
):
    category = await category_service.create_category(db, payload)
    await commit_async(db)
    return category


@router.put(
    "/{category_id}",
    response_model=CategoryRead,
    dependencies=[Depends(get_current_admin)],
)
async def admin_update(
    category_id: str = Path(...),
    payload: CategoryUpdate = ...,
    db: AsyncSession = Depends(get_async_db),
):
    try:
        category_uuid = uuid.UUID(str(category_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid category id") from exc

    category = await category_service.get_category_by_id(db, str(category_uuid))
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    updated = await category_service.update_category(db, category, payload)
    await commit_async(db)
    return updated
