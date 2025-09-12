# app/schemas/variant.py
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional

class VariantBase(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64)
    barcode: Optional[str] = Field(None, max_length=64)
    size_label: str = Field(..., min_length=1, max_length=24)
    color_name: str = Field(..., min_length=1, max_length=32)
    color_hex: Optional[str] = Field(None, min_length=4, max_length=7)  # p.ej. "#000" o "#000000"

    stock_on_hand: int = Field(0, ge=0)
    stock_reserved: int = Field(0, ge=0)

    price_override: Optional[float] = Field(None, ge=0)

    active: bool = True

    @field_validator("color_hex")
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("#"):
            raise ValueError("color_hex debe comenzar con #")
        if len(v) not in (4, 7):
            raise ValueError("color_hex debe ser #RGB o #RRGGBB")
        return v


class VariantCreate(VariantBase):
    pass


class VariantUpdate(BaseModel):
    barcode: Optional[str] = Field(None, max_length=64)
    size_label: Optional[str] = Field(None, min_length=1, max_length=24)
    color_name: Optional[str] = Field(None, min_length=1, max_length=32)
    color_hex: Optional[str] = Field(None, min_length=4, max_length=7)

    stock_on_hand: Optional[int] = Field(None, ge=0)
    stock_reserved: Optional[int] = Field(None, ge=0)

    price_override: Optional[float] = Field(None, ge=0)

    active: Optional[bool] = None

    @field_validator("color_hex")
    @classmethod
    def validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith("#"):
            raise ValueError("color_hex debe comenzar con #")
        if len(v) not in (4, 7):
            raise ValueError("color_hex debe ser #RGB o #RRGGBB")
        return v


class VariantRead(VariantBase):
    id: str
    product_id: str

    # Pydantic v2: reemplaza class Config
    model_config = ConfigDict(from_attributes=True)
