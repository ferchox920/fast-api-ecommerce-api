from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import ProductEngagementDaily, ProductRanking
from app.models.promotion import Promotion, PromotionStatus
from app.models.loyalty import LoyaltyProfile
from app.models.order import Order


async def overview(db: AsyncSession, days: int = 7) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    total_revenue_result = await db.execute(
        select(func.coalesce(func.sum(ProductEngagementDaily.revenue), 0)).where(
            ProductEngagementDaily.date >= start.date()
        )
    )
    total_revenue = total_revenue_result.scalar_one()
    total_orders = (await db.execute(select(func.count(Order.id)))).scalar_one()
    pop_mix = await _exposure_mix(db)
    loyalty_distribution = await _loyalty_distribution(db)

    return {
        "period": {
            "start": start.isoformat(),
            "end": datetime.now(timezone.utc).isoformat(),
        },
        "kpis": {
            "total_revenue": float(total_revenue or 0),
            "orders": total_orders,
            "average_exposure_mix": pop_mix,
            "loyalty_distribution": loyalty_distribution,
        },
    }


async def _exposure_mix(db: AsyncSession) -> dict:
    stmt = select(ProductRanking)
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return {"popular": 0.0, "strategic": 0.0}
    popular = sum(float(r.popularity_score) for r in rows)
    strategic = sum(float(r.cold_score) for r in rows)
    total = popular + strategic
    if total == 0:
        return {"popular": 0.0, "strategic": 0.0}
    return {
        "popular": round(popular / total, 3),
        "strategic": round(strategic / total, 3),
    }


async def _loyalty_distribution(db: AsyncSession) -> dict:
    stmt = select(LoyaltyProfile.level, func.count(LoyaltyProfile.customer_id)).group_by(LoyaltyProfile.level)
    rows = await db.execute(stmt)
    return {row.level: row[1] for row in rows.all()}


async def promotions_dashboard(db: AsyncSession) -> dict:
    rows = (await db.execute(select(Promotion))).scalars().all()
    return {
        "count": len(rows),
        "active": [str(p.id) for p in rows if p.status == PromotionStatus.active],
    }
