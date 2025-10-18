from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.engagement import CustomerEngagementDaily
from app.models.loyalty import LoyaltyLevel, LoyaltyProfile, LoyaltyHistory
from app.schemas.engagement import EventCreate
from app.schemas.loyalty import LoyaltyAdjustPayload, LoyaltyRedeemPayload
from app.services import notification_service
from app.services.event_bus import emit_loyalty_event

DEFAULT_LEVELS = [
    {"level": "bronze", "min_points": 0, "perks_json": {"label": "Bronce"}},
    {"level": "silver", "min_points": 500, "perks_json": {"discount_percent": 5}},
    {"level": "gold", "min_points": 1500, "perks_json": {"discount_percent": 10, "free_shipping": True}},
    {"level": "diamond", "min_points": 3000, "perks_json": {"discount_percent": 15, "priority_support": True}},
]


def ensure_levels(db: Session) -> None:
    for level in DEFAULT_LEVELS:
        if not db.get(LoyaltyLevel, level["level"]):
            db.add(LoyaltyLevel(level=level["level"], min_points=level["min_points"], perks_json=level["perks_json"]))
    db.commit()


def _get_profile(db: Session, user_id: str) -> LoyaltyProfile:
    profile = db.get(LoyaltyProfile, user_id)
    if not profile:
        ensure_levels(db)
        profile = LoyaltyProfile(customer_id=user_id, level="bronze", points=0, progress_json={})
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _determine_level(db: Session, points: int) -> LoyaltyLevel:
    levels = db.execute(select(LoyaltyLevel).order_by(LoyaltyLevel.min_points.desc())).scalars().all()
    for level in levels:
        if points >= level.min_points:
            return level
    return levels[-1]


def process_purchase_event(db: Session, event: EventCreate, event_date: date) -> None:
    # INTEGRATION: user_id puede ser anónimo (cookie/device_id); reconciliar al loguearse.
    if not event.user_id:
        return
    profile = _get_profile(db, str(event.user_id))
    quantity = event.metadata.quantity if event.metadata and event.metadata.quantity else 1
    base_points = max(10, int(event.price or 0))
    points_delta = base_points * quantity
    profile.points += points_delta

    new_level = _determine_level(db, profile.points)
    prev_level = profile.level
    profile.level = new_level.level

    history = LoyaltyHistory(
        customer_id=str(event.user_id),
        level=profile.level,
        points_delta=points_delta,
        reason="purchase",
        details={"product_id": str(event.product_id)},
    )
    db.add(history)

    daily = (
        db.execute(
            select(CustomerEngagementDaily)
            .where(CustomerEngagementDaily.customer_id == str(event.user_id))
            .where(CustomerEngagementDaily.date == event_date)
        ).scalar_one_or_none()
    )
    if daily:
        daily.points_earned += points_delta

    db.add(profile)
    db.commit()
    db.refresh(profile)

    if prev_level != new_level.level:
        notification_service.notify_loyalty_upgrade(db, profile, prev_level)
        emit_loyalty_event(
            "loyalty_upgrade",
            {
                "user_id": profile.customer_id,
                "previous_level": prev_level,
                "new_level": profile.level,
                "points": profile.points,
            },
        )


def get_profile(db: Session, user_id: str) -> LoyaltyProfile:
    return _get_profile(db, user_id)


def apply_adjustment(db: Session, payload: LoyaltyAdjustPayload) -> LoyaltyProfile:
    profile = _get_profile(db, payload.user_id)
    profile.points = max(0, profile.points + payload.points_delta)
    new_level = _determine_level(db, profile.points)
    prev_level = profile.level
    profile.level = new_level.level

    history = LoyaltyHistory(
        customer_id=payload.user_id,
        level=profile.level,
        points_delta=payload.points_delta,
        reason=payload.reason or "adjustment",
        details=payload.metadata,
    )
    db.add(history)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    if prev_level != profile.level:
        notification_service.notify_loyalty_upgrade(db, profile, prev_level)
        emit_loyalty_event(
            "loyalty_upgrade",
            {
                "user_id": profile.customer_id,
                "previous_level": prev_level,
                "new_level": profile.level,
                "points": profile.points,
            },
        )

    return profile


def redeem_reward(db: Session, payload: LoyaltyRedeemPayload) -> LoyaltyProfile:
    if not payload.user_id:
        raise ValueError("user_required")
    profile = _get_profile(db, payload.user_id)
    if profile.points < payload.points:
        raise ValueError("insufficient_points")

    profile.points -= payload.points
    history = LoyaltyHistory(
        customer_id=profile.customer_id,
        level=profile.level,
        points_delta=-payload.points,
        reason="redeem",
        details={
            "reward_code": payload.reward_code,
            "metadata": payload.metadata,
        },
    )
    db.add(history)
    db.add(profile)
    db.commit()
    db.refresh(profile)

    emit_loyalty_event(
        "loyalty_redeem",
        {
            "user_id": profile.customer_id,
            "points": payload.points,
            "reward_code": payload.reward_code,
        },
    )
    return profile


def list_levels(db: Session):
    ensure_levels(db)
    return db.execute(select(LoyaltyLevel).order_by(LoyaltyLevel.min_points)).scalars().all()

