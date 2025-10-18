from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ExposureItem(BaseModel):
    product_id: UUID
    reason: List[str] = Field(default_factory=list)
    badges: List[str] = Field(default_factory=list)


class ExposureResponse(BaseModel):
    context: str
    user_id: Optional[str] = None
    category_id: Optional[UUID] = None
    generated_at: datetime
    expires_at: datetime
    mix: List[ExposureItem] = Field(default_factory=list)
