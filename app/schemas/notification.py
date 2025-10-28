from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class NotificationCreate(BaseModel):
    user_id: UUID
    type: str
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=2000)
    payload: dict | None = None


class NotificationRead(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    title: str
    message: str
    payload: dict | None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    is_read: bool
