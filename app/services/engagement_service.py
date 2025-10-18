from __future__ import annotations

from collections import defaultdict
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.engagement import (
    ProductEngagementDaily,
    CustomerEngagementDaily,
)
from app.schemas.engagement import EventCreate

# INTEGRATION: Event schema se alinea con frontend tracker (dataLayer/SDK).
_EVENT_QUEUE: dict[datetime, list[EventCreate]] = defaultdict(list)
_DEDUP_CACHE: set[str] = set()
_DEDUP_TTL = 10000


def _today_utc(ts: Optional[datetime] = None):
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.date()


def _bucket_start(ts: datetime | None) -> datetime:
    if ts is None:
        ts = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.replace(minute=0, second=0, microsecond=0)


def _dedup_key(event: EventCreate, bucket: datetime) -> str:
    user_component = str(event.user_id or event.session_id or "anon")
    product_component = str(event.product_id)
    return f"{user_component}:{product_component}:{bucket.isoformat()}:{event.event_type}"


def _enqueue_event(event: EventCreate) -> Optional[datetime]:
    bucket = _bucket_start(event.timestamp)
    key = _dedup_key(event, bucket)
    if key in _DEDUP_CACHE:
        return None
    _EVENT_QUEUE[bucket].append(event)
    _DEDUP_CACHE.add(key)
    if len(_DEDUP_CACHE) > _DEDUP_TTL:
        _DEDUP_CACHE.pop()
    return bucket


def _apply_aggregate(db: Session, product_id, date, views=0, clicks=0, carts=0, purchases=0, revenue=Decimal("0")):
    product_uuid = uuid.UUID(str(product_id))
    record = (
        db.execute(
            select(ProductEngagementDaily)
            .where(ProductEngagementDaily.product_id == product_uuid)
            .where(ProductEngagementDaily.date == date)
        ).scalar_one_or_none()
    )
    if not record:
        record = ProductEngagementDaily(product_id=product_uuid, date=date)
        db.add(record)
        db.flush()

    record.views += views
    record.clicks += clicks
    record.carts += carts
    record.purchases += purchases
    record.revenue = (record.revenue or Decimal("0")) + revenue

    return record


def _apply_customer(db: Session, user_id: str, date, views=0, clicks=0, carts=0, purchases=0, points=0):
    record = (
        db.execute(
            select(CustomerEngagementDaily)
            .where(CustomerEngagementDaily.customer_id == user_id)
            .where(CustomerEngagementDaily.date == date)
        ).scalar_one_or_none()
    )
    if not record:
        record = CustomerEngagementDaily(customer_id=user_id, date=date)
        db.add(record)
        db.flush()

    record.views += views
    record.clicks += clicks
    record.carts += carts
    record.purchases += purchases
    record.points_earned += points


def _flush_bucket(db: Session, bucket: datetime) -> None:
    events = _EVENT_QUEUE.pop(bucket, [])
    if not events:
        return

    aggregates: dict[str, dict[str, Decimal | int]] = {}
    customer_agg: dict[str, dict[str, int]] = {}
    for event in events:
        product_key = str(event.product_id)
        info = aggregates.setdefault(product_key, {"views": 0, "clicks": 0, "carts": 0, "purchases": 0, "revenue": Decimal("0")})
        customer_id = str(event.user_id) if event.user_id else None
        metadata_qty = event.metadata.quantity if event.metadata and event.metadata.quantity else 1

        if event.event_type == "view":
            info["views"] += 1
            if customer_id:
                customer_agg.setdefault(customer_id, {"views": 0, "clicks": 0, "carts": 0, "purchases": 0, "points": 0})["views"] += 1
        elif event.event_type == "click":
            info["clicks"] += 1
            if customer_id:
                customer_agg.setdefault(customer_id, {"views": 0, "clicks": 0, "carts": 0, "purchases": 0, "points": 0})["clicks"] += 1
        elif event.event_type == "add_to_cart":
            info["carts"] += metadata_qty
            if customer_id:
                bucket_values = customer_agg.setdefault(customer_id, {"views": 0, "clicks": 0, "carts": 0, "purchases": 0, "points": 0})
                bucket_values["carts"] += metadata_qty
        elif event.event_type == "purchase":
            info["purchases"] += metadata_qty
            # INTEGRATION: En purchase, revenue viene del backend de checkout (no del frontend).
            if event.price is not None:
                info["revenue"] += Decimal(str(event.price)) * Decimal(metadata_qty)
            if customer_id:
                bucket_values = customer_agg.setdefault(customer_id, {"views": 0, "clicks": 0, "carts": 0, "purchases": 0, "points": 0})
                bucket_values["purchases"] += metadata_qty
                bucket_values["points"] += metadata_qty * 10

    date_actual = bucket.date()
    for product_key, values in aggregates.items():
        record = _apply_aggregate(
            db,
            product_id=product_key,
            date=date_actual,
            views=int(values["views"]),
            clicks=int(values["clicks"]),
            carts=int(values["carts"]),
            purchases=int(values["purchases"]),
            revenue=values["revenue"],
        )
        db.add(record)

    for customer_id, values in customer_agg.items():
        _apply_customer(
            db,
            user_id=customer_id,
            date=date_actual,
            views=values["views"],
            clicks=values["clicks"],
            carts=values["carts"],
            purchases=values["purchases"],
            points=values["points"],
        )

    db.commit()


def record_event(db: Session, payload: EventCreate) -> Optional[ProductEngagementDaily]:
    bucket = _enqueue_event(payload)
    if bucket is None:
        return None

    _flush_bucket(db, bucket)

    record = (
        db.execute(
            select(ProductEngagementDaily)
            .where(ProductEngagementDaily.product_id == payload.product_id)
            .where(ProductEngagementDaily.date == _today_utc(payload.timestamp))
        ).scalar_one_or_none()
    )

    if payload.event_type == "purchase" and payload.user_id:
        # INTEGRATION: user_id puede ser anónimo (cookie/device_id); reconciliar al loguearse.
        from app.services import loyalty_service

        loyalty_service.process_purchase_event(db, payload, _today_utc(payload.timestamp))

    return record


def get_product_engagement(db: Session, product_id, day=None):
    stmt = select(ProductEngagementDaily).where(ProductEngagementDaily.product_id == product_id)
    if day:
        stmt = stmt.where(ProductEngagementDaily.date == day)
    return db.execute(stmt).scalars().all()


def get_customer_engagement(db: Session, user_id, day=None):
    stmt = select(CustomerEngagementDaily).where(CustomerEngagementDaily.customer_id == str(user_id))
    if day:
        stmt = stmt.where(CustomerEngagementDaily.date == day)
    return db.execute(stmt).scalars().all()


def process_hourly_events(db: Session) -> None:
    """Worker que agrega eventos por bucket horario y los vuelca al agregado diario."""

    # TODO: Si Kafka, usar compaction por key=product_id:date.
    for bucket in list(_EVENT_QUEUE.keys()):
        # pseudo:
        # for bucket in hourly_buckets:
        #     metrics = reduce(events[bucket])
        #     upsert(product_engagement_daily, metrics)
        _flush_bucket(db, bucket)


