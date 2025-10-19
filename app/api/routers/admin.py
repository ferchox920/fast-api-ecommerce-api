from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.schemas.user import UserRead, UserCreate
from app.models.user import User as UserModel
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_async_db),
    _: UserModel = Depends(get_current_admin),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return await admin_service.list_users(db, skip=skip, limit=limit)

@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    payload: UserCreate,
    is_superuser: bool = Query(False, description="Crear como admin si true"),
    db: AsyncSession = Depends(get_async_db),
    _: UserModel = Depends(get_current_admin),
):
    try:
        user = await admin_service.create_user_as_admin(db, payload, make_superuser=is_superuser)
        await commit_async(db)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

@router.patch("/users/{user_id}/role", response_model=UserRead)
async def set_admin_role(
    user_id: str = Path(...),
    make_admin: bool = Query(..., description="true = admin, false = no admin"),
    db: AsyncSession = Depends(get_async_db),
    _: UserModel = Depends(get_current_admin),
):
    user = await admin_service.set_admin_role(db, user_id, make_admin)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await commit_async(db)
    return user

@router.patch("/users/{user_id}/active", response_model=UserRead)
async def set_active(
    user_id: str = Path(...),
    active: bool = Query(..., description="true = activar, false = desactivar"),
    db: AsyncSession = Depends(get_async_db),
    _: UserModel = Depends(get_current_admin),
):
    user = await admin_service.set_active(db, user_id, active)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await commit_async(db)
    return user
