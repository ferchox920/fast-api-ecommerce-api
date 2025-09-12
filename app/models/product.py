from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Numeric, ForeignKey, DateTime, func, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.session import Base

# --- Clasificación ---
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    products = relationship("Product", back_populates="category", cascade="all, delete-orphan")


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)  # <-- NUEVO
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    products = relationship("Product", back_populates="brand")


# --- Producto (atributos generales, no “SKU”) ---
class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)

    # descripción y detalles textiles
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    material:    Mapped[str | None] = mapped_column(String(140), nullable=True)
    care:        Mapped[str | None] = mapped_column(String, nullable=True)

    # segmentación de moda
    gender:  Mapped[str | None] = mapped_column(String(16), nullable=True)
    season:  Mapped[str | None] = mapped_column(String(16), nullable=True)
    fit:     Mapped[str | None] = mapped_column(String(32), nullable=True)

    # precios base
    price:    Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str]   = mapped_column(String(3), default="ARS", nullable=False)

    # relaciones
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())

    category = relationship(Category, back_populates="products", lazy="joined")
    brand = relationship(Brand, back_populates="products", lazy="joined")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.sort_order")


# --- Variante (talle/color/SKU/stock) ---
class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    sku:        Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    barcode:    Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_label: Mapped[str] = mapped_column(String(24), nullable=False)
    color_name: Mapped[str] = mapped_column(String(32), nullable=False)
    color_hex:  Mapped[str | None] = mapped_column(String(7), nullable=True)

    stock_on_hand:  Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stock_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    price_override: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())

    product = relationship(Product, back_populates="variants")


# --- Imágenes del producto ---
class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )

    url:       Mapped[str] = mapped_column(String(512), nullable=False)
    alt_text:  Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product = relationship(Product, back_populates="images")
