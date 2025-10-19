from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Security, status, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.wish import WishCreate, WishRead, WishWithNotifications
from app.services import wish_service
from app.services.exceptions import ServiceError

router = APIRouter(prefix="/wishes", tags=["wishes"])


@router.get("", response_model=list[WishWithNotifications])
def list_my_wishes(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:read"]),
) -> list[WishWithNotifications]:
    wishes = wish_service.list_user_wishes(db, current_user.id)
    return [WishWithNotifications.model_validate(wish, from_attributes=True) for wish in wishes]


@router.post("", response_model=WishRead, status_code=status.HTTP_201_CREATED)
def create_wish(
    payload: WishCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:write"]),
) -> WishRead:
    try:
        wish = wish_service.create_wish(db, current_user.id, payload)
        db.commit()
    except ServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    db.refresh(wish)
    return WishRead.model_validate(wish, from_attributes=True)


@router.delete(
    "/{wish_id}",
    status_code=status.HTTP_200_OK,
)
def delete_wish(
    wish_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:write"]),
) -> None:
    try:
        wish_service.delete_wish(db, wish_id, current_user.id)
        db.commit()
    except ServiceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {"detail": "Wish deleted"}
