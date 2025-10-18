from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class CartItemCreate(BaseModel):
    variant_id: UUID | str
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
    user_id: str | None
    guest_token: str | None
    status: str
    currency: str
    subtotal_amount: float
    discount_amount: float
    total_amount: float
    created_at: datetime
    updated_at: datetime | None
    items: List[CartItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
