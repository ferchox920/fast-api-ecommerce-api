from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import flush_async, refresh_async
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


async def ensure_levels(db: AsyncSession) -> None:
    levels_created = False
    for level in DEFAULT_LEVELS:
        existing = await db.get(LoyaltyLevel, level["level"])
        if not existing:
            db.add(LoyaltyLevel(level=level["level"], min_points=level["min_points"], perks_json=level["perks_json"]))
            levels_created = True
    if levels_created:
        await flush_async(db)


async def _get_profile(db: AsyncSession, user_id: str) -> LoyaltyProfile:
    profile = await db.get(LoyaltyProfile, user_id)
    if not profile:
        await ensure_levels(db)
        profile = LoyaltyProfile(customer_id=user_id, level="bronze", points=0, progress_json={})
        db.add(profile)
        await flush_async(db, profile)
        await refresh_async(db, profile)
    return profile


async def _determine_level(db: AsyncSession, points: int) -> LoyaltyLevel:
    result = await db.execute(select(LoyaltyLevel).order_by(LoyaltyLevel.min_points.desc()))
    levels = result.scalars().all()
    if not levels:
        await ensure_levels(db)
        result = await db.execute(select(LoyaltyLevel).order_by(LoyaltyLevel.min_points.desc()))
        levels = result.scalars().all()
    if not levels:
        raise RuntimeError("No loyalty levels configured")
    for level in levels:
        if points >= level.min_points:
            return level
    return levels[-1]


async def process_purchase_event(db: AsyncSession, event: EventCreate, event_date: date) -> None:
    if not event.user_id:
        return
    profile = await _get_profile(db, str(event.user_id))
    quantity = event.metadata.quantity if event.metadata and event.metadata.quantity else 1
    base_points = max(10, int(event.price or 0))
    points_delta = base_points * quantity
    profile.points += points_delta

    new_level = await _determine_level(db, profile.points)
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

    result = await db.execute(
        select(CustomerEngagementDaily)
        .where(CustomerEngagementDaily.customer_id == str(event.user_id))
        .where(CustomerEngagementDaily.date == event_date)
    )
    daily = result.scalar_one_or_none()
    if daily:
        daily.points_earned += points_delta

    db.add(profile)
    await flush_async(db, profile, history)
    await refresh_async(db, profile)

    if prev_level != new_level.level:
        await notification_service.notify_loyalty_upgrade(db, profile, prev_level)
        emit_loyalty_event(
            "loyalty_upgrade",
            {
                "user_id": profile.customer_id,
                "previous_level": prev_level,
                "new_level": profile.level,
                "points": profile.points,
            },
        )


async def get_profile(db: AsyncSession, user_id: str) -> LoyaltyProfile:
    return await _get_profile(db, user_id)


async def apply_adjustment(db: AsyncSession, payload: LoyaltyAdjustPayload) -> LoyaltyProfile:
    profile = await _get_profile(db, payload.user_id)
    profile.points = max(0, profile.points + payload.points_delta)
    new_level = await _determine_level(db, profile.points)
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
    await flush_async(db, profile, history)
    await refresh_async(db, profile)

    if prev_level != profile.level:
        await notification_service.notify_loyalty_upgrade(db, profile, prev_level)
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


async def redeem_reward(db: AsyncSession, payload: LoyaltyRedeemPayload) -> LoyaltyProfile:
    if not payload.user_id:
        raise ValueError("user_required")
    profile = await _get_profile(db, payload.user_id)
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
    await flush_async(db, profile, history)
    await refresh_async(db, profile)

    emit_loyalty_event(
        "loyalty_redeem",
        {
            "user_id": profile.customer_id,
            "points": payload.points,
            "reward_code": payload.reward_code,
        },
    )
    return profile


async def list_levels(db: AsyncSession):
    await ensure_levels(db)
    result = await db.execute(select(LoyaltyLevel).order_by(LoyaltyLevel.min_points))
    return result.scalars().all()
