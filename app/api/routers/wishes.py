from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Security, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.wish import WishCreate, WishRead, WishWithNotifications
from app.services import wish_service
from app.services.exceptions import ServiceError

router = APIRouter(prefix="/wishes", tags=["wishes"])


@router.get("", response_model=list[WishWithNotifications])
async def list_my_wishes(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["users:read"]),
) -> list[WishWithNotifications]:
    wishes = await wish_service.list_user_wishes(db, current_user.id)
    return [WishWithNotifications.model_validate(wish, from_attributes=True) for wish in wishes]


@router.post("", response_model=WishRead, status_code=status.HTTP_201_CREATED)
async def create_wish(
    payload: WishCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["users:write"]),
) -> WishRead:
    try:
        wish = await wish_service.create_wish(db, current_user.id, payload)
        await db.commit()
        await db.refresh(wish)
    except ServiceError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="wish_create_failed") from exc
    return WishRead.model_validate(wish, from_attributes=True)


@router.delete(
    "/{wish_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_wish(
    wish_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["users:write"]),
) -> dict:
    try:
        await wish_service.delete_wish(db, wish_id, current_user.id)
        await db.commit()
    except ServiceError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="wish_delete_failed") from exc
    return {"detail": "Wish deleted"}
