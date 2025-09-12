from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, ConfigDict

# --- Category / Brand ---
class CategoryCreate(BaseModel):
    name: str
    slug: str | None = None  # opcional

class CategoryRead(CategoryCreate):
    id: UUID
    active: bool = True
    model_config = ConfigDict(from_attributes=True)

class BrandCreate(BaseModel):
    name: str
    slug: str | None = None  # opcional

class BrandRead(BrandCreate):
    id: UUID
    active: bool = True
    model_config = ConfigDict(from_attributes=True)

# --- Images ---
class ProductImageCreate(BaseModel):
    url: HttpUrl
    alt_text: str | None = None
    is_primary: bool = False
    sort_order: int = 0

class ProductImageRead(ProductImageCreate):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# --- Variants ---
class ProductVariantBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    size_label: str = Field(min_length=1, max_length=24)  # "S","M","L","42"
    color_name: str = Field(min_length=1, max_length=32)
    color_hex: str | None = Field(default=None, pattern=r"^#([0-9a-fA-F]{6})$")

    stock_on_hand: int = Field(ge=0, default=0)
    stock_reserved: int = Field(ge=0, default=0)
    price_override: float | None = Field(default=None, ge=0)

    barcode: str | None = Field(default=None, max_length=64)
    active: bool = True

class ProductVariantCreate(ProductVariantBase):
    pass

class ProductVariantUpdate(BaseModel):
    size_label: str | None = None
    color_name: str | None = None
    color_hex: str | None = Field(default=None, pattern=r"^#([0-9a-fA-F]{6})$")
    stock_on_hand: int | None = Field(default=None, ge=0)
    stock_reserved: int | None = Field(default=None, ge=0)
    price_override: float | None = Field(default=None, ge=0)
    barcode: str | None = None
    active: bool | None = None

class ProductVariantRead(ProductVariantBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)

# --- Product ---
class ProductBase(BaseModel):
    title: str
    slug: str | None = None
    description: str | None = None
    material: str | None = None
    care: str | None = None
    gender: str | None = Field(default=None, description='men|women|unisex|kids')
    season: str | None = None
    fit: str | None = None
    price: float = Field(ge=0)
    currency: str = Field(default="ARS", min_length=3, max_length=3)
    # En Create/Update aceptamos string; en Read redefinimos como UUID
    category_id: str | None = None
    brand_id: str | None = None
    active: bool = True

class ProductCreate(ProductBase):
    variants: List[ProductVariantCreate] = Field(default_factory=list)
    images:   List[ProductImageCreate]   = Field(default_factory=list)

class ProductUpdate(BaseModel):
    title: str | None = None
    slug: str | None = None
    description: str | None = None
    material: str | None = None
    care: str | None = None
    gender: str | None = None
    season: str | None = None
    fit: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category_id: str | None = None
    brand_id: str | None = None
    active: bool | None = None

class ProductRead(ProductBase):
    id: UUID
    # IDs como UUID para validar con el ORM
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    # Relaciones anidadas (ya definidas arriba, no necesitan forward-ref string)
    category: CategoryRead | None = None
    brand: BrandRead | None = None

    variants: List[ProductVariantRead] = []
    images:   List[ProductImageRead]   = []
    model_config = ConfigDict(from_attributes=True)
