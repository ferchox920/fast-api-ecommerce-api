# app/models/cart.py
import uuid
import enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Enum, DateTime, func, Numeric, Integer, ForeignKey, UniqueConstraint, Index

from app.db.session import Base
from app.db.types import GUID  # 👈 nuestro tipo UUID portable


class CartStatus(str, enum.Enum):
    active = "active"
    converted = "converted"
    abandoned = "abandoned"


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (
        UniqueConstraint("guest_token", name="uq_carts_guest_token"),
        Index("ix_carts_user_id_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    guest_token: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[CartStatus] = mapped_column(Enum(CartStatus), default=CartStatus.active, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="ARS", nullable=False)

    subtotal_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan", passive_deletes=True
    )


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4, nullable=False)
    cart_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cart = relationship("Cart", back_populates="items")
