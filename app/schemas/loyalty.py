from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LoyaltyProfileRead(BaseModel):
    user_id: str = Field(validation_alias="customer_id")
    level: str
    points: int
    progress_json: dict
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class LoyaltyAdjustPayload(BaseModel):
    user_id: str
    points_delta: int = Field(..., ge=-100000, le=100000)
    reason: Optional[str] = None
    metadata: dict | None = None


class LoyaltyRedeemPayload(BaseModel):
    user_id: Optional[str] = None
    points: int = Field(..., gt=0)
    reward_code: Optional[str] = None
    metadata: dict | None = None
