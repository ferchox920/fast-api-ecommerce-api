import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LoyaltyLevel(Base):
    __tablename__ = "loyalty_levels"

    level: Mapped[str] = mapped_column(String(50), primary_key=True)
    min_points: Mapped[int] = mapped_column(Integer, nullable=False)
    perks_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class LoyaltyProfile(Base):
    __tablename__ = "loyalty_profile"
    __table_args__ = (Index("ix_loyalty_profile_level", "level"),)

    customer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    level: Mapped[str] = mapped_column(String(50), ForeignKey("loyalty_levels.level", ondelete="RESTRICT"), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    level_rel: Mapped[LoyaltyLevel] = relationship("LoyaltyLevel")

    # INTEGRATION: 'progress_json' compatibiliza con futuras misiones/retos (gamificación).


class LoyaltyHistory(Base):
    __tablename__ = "loyalty_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    points_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
