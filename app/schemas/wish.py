from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class WishBase(BaseModel):
    product_id: UUID
    desired_price: Decimal | None = Field(default=None, ge=0)
    notify_discount: bool = True


class WishCreate(WishBase):
    pass


class WishRead(WishBase):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WishNotificationRead(BaseModel):
    id: UUID
    notification_type: str
    message: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WishWithNotifications(WishRead):
    notifications: list[WishNotificationRead] = []
