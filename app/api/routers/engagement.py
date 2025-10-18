from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.engagement import EventCreate, ProductEngagementRead, CustomerEngagementRead
from app.services import engagement_service

router = APIRouter(prefix="/events", tags=["engagement"])


# INTEGRATION: Frontend tracking enviará POST /events con {event_type, product_id, user_id, ts, metadata}.
@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ProductEngagementRead)
def ingest_event(payload: EventCreate, db: Session = Depends(get_db)):
    record = engagement_service.record_event(db, payload)
    if record is None:
        return ProductEngagementRead(
            product_id=payload.product_id,
            date=payload.timestamp.date() if payload.timestamp else datetime.utcnow().date(),
            views=0,
            clicks=0,
            carts=0,
            purchases=0,
            revenue=0.0,
        )
    return ProductEngagementRead(
        product_id=record.product_id,
        date=record.date,
        views=record.views,
        clicks=record.clicks,
        carts=record.carts,
        purchases=record.purchases,
        revenue=float(record.revenue or 0),
    )


@router.get("/products/{product_id}", response_model=list[ProductEngagementRead])
def get_product_engagement(product_id: UUID, day: date | None = Query(default=None), db: Session = Depends(get_db)):
    records = engagement_service.get_product_engagement(db, product_id, day)
    return [
        ProductEngagementRead(
            product_id=r.product_id,
            date=r.date,
            views=r.views,
            clicks=r.clicks,
            carts=r.carts,
            purchases=r.purchases,
            revenue=float(r.revenue or 0),
        )
        for r in records
    ]


@router.get("/customers/{user_id}", response_model=list[CustomerEngagementRead])
def get_customer_engagement(user_id: UUID, day: date | None = Query(default=None), db: Session = Depends(get_db)):
    records = engagement_service.get_customer_engagement(db, user_id, day)
    return [
        CustomerEngagementRead(
            customer_id=r.customer_id,
            date=r.date,
            views=r.views,
            clicks=r.clicks,
            carts=r.carts,
            purchases=r.purchases,
            points_earned=r.points_earned,
        )
        for r in records
    ]


