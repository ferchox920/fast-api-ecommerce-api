# app/schemas/cart.py
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# Evitá ciclos importando el Enum desde un módulo común.
# Si aún no lo tenés, creá app/domain/enums.py con CartStatus.
from app.domain.enums import CartStatus


class CartItemCreate(BaseModel):
    # Pydantic v2 parsea strings UUID sin problema si el tipo es UUID
    variant_id: UUID
    quantity: int = Field(..., gt=0)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., gt=0)


class CartCreate(BaseModel):
    guest_token: Optional[str] = Field(default=None, max_length=120)
    currency: str = Field(default="ARS", min_length=3, max_length=3)


class CartItemRead(BaseModel):
    id: UUID
    variant_id: UUID
    quantity: int
    unit_price: float
    line_total: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CartRead(BaseModel):
    id: UUID
    # <--- antes era str | None: cámbialo a UUID | None
    user_id: UUID | None
    guest_token: str | None

    # <--- antes era str: tipalo con el Enum real
    status: CartStatus
    currency: str

    subtotal_amount: float
    discount_amount: float
    total_amount: float

    created_at: datetime
    updated_at: datetime | None

    items: List[CartItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
