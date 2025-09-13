# app/schemas/inventory.py
from pydantic import BaseModel
from pydantic.config import ConfigDict
from typing import Literal
from uuid import UUID
from datetime import datetime

MovementType = Literal["receive", "adjust", "reserve", "release", "sale"]

class MovementCreate(BaseModel):
    type: MovementType
    quantity: int  # Field(gt=0) si no quieres permitir <=0 desde la API
    reason: str | None = None

class MovementRead(BaseModel):
    id: UUID
    type: MovementType
    quantity: int
    reason: str | None
    created_at: datetime

    # Pydantic v2: evita el warning y habilita from_attributes
    model_config = ConfigDict(from_attributes=True)
