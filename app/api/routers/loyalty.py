from typing import Optional

from fastapi import APIRouter, Depends, Query, Security, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.loyalty import LoyaltyProfileRead, LoyaltyAdjustPayload, LoyaltyRedeemPayload
from app.services import loyalty_service

router = APIRouter(prefix="/loyalty", tags=["loyalty"])


@router.get("/profile", response_model=LoyaltyProfileRead)
def get_profile(
    user_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    target_user = user_id or current_user.id
    profile = loyalty_service.get_profile(db, target_user)
    return LoyaltyProfileRead(
        user_id=profile.customer_id,
        level=profile.level,
        points=profile.points,
        progress_json=profile.progress_json,
        updated_at=profile.updated_at,
    )


@router.post("/adjust", response_model=LoyaltyProfileRead)
def adjust_profile(
    payload: LoyaltyAdjustPayload,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    profile = loyalty_service.apply_adjustment(db, payload)
    return LoyaltyProfileRead(
        user_id=profile.customer_id,
        level=profile.level,
        points=profile.points,
        progress_json=profile.progress_json,
        updated_at=profile.updated_at,
    )


@router.post("/redeem", response_model=LoyaltyProfileRead)
def redeem_reward(
    payload: LoyaltyRedeemPayload,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    target_user = payload.user_id or current_user.id
    redeem_payload = LoyaltyRedeemPayload(
        user_id=target_user,
        points=payload.points,
        reward_code=payload.reward_code,
        metadata=payload.metadata,
    )
    try:
        profile = loyalty_service.redeem_reward(db, redeem_payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return LoyaltyProfileRead(
        user_id=profile.customer_id,
        level=profile.level,
        points=profile.points,
        progress_json=profile.progress_json,
        updated_at=profile.updated_at,
    )


@router.get("/levels")
def list_levels(db: Session = Depends(get_db)):
    levels = loyalty_service.list_levels(db)
    return [
        {
            "level": level.level,
            "min_points": level.min_points,
            "perks_json": level.perks_json,
        }
        for level in levels
    ]
