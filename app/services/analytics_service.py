from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.engagement import ProductEngagementDaily, ProductRanking
from app.models.promotion import Promotion, PromotionStatus
from app.models.loyalty import LoyaltyProfile
from app.models.order import Order


def overview(db: Session, days: int = 7) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=days)
    total_revenue = (
        db.execute(
            select(func.coalesce(func.sum(ProductEngagementDaily.revenue), 0))
            .where(ProductEngagementDaily.date >= start.date())
        ).scalar_one()
    )
    total_orders = db.execute(select(func.count(Order.id))).scalar_one()
    pop_mix = _exposure_mix(db)
    loyalty_distribution = _loyalty_distribution(db)

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


def _exposure_mix(db: Session) -> dict:
    stmt = select(ProductRanking)
    rows = db.execute(stmt).scalars().all()
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


def _loyalty_distribution(db: Session) -> dict:
    stmt = select(LoyaltyProfile.level, func.count(LoyaltyProfile.customer_id)).group_by(LoyaltyProfile.level)
    return {row.level: row[1] for row in db.execute(stmt).all()}


def promotions_dashboard(db: Session) -> dict:
    rows = db.execute(select(Promotion)).scalars().all()
    return {
        "count": len(rows),
        "active": [str(p.id) for p in rows if p.status == PromotionStatus.active],
    }
