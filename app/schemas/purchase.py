from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Literal, Optional
from uuid import UUID
from datetime import datetime

POStatus = Literal["draft", "placed", "partially_received", "received", "cancelled"]

# ----- Create -----
class POLineCreate(BaseModel):
    variant_id: UUID | str
    quantity: int = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)

class POCreate(BaseModel):
    supplier_id: UUID | str
    currency: str = Field(default="ARS", min_length=3, max_length=3)
    lines: List[POLineCreate] = Field(default_factory=list)

# ----- Read -----
class POLineRead(BaseModel):
    id: UUID
    variant_id: UUID
    # mapear ORM.qty_ordered -> quantity que esperan los tests
    quantity: int = Field(validation_alias="qty_ordered")
    # opcional si más tarde usas qty_received en la API de lectura:
    # quantity_received: int = Field(validation_alias="qty_received")
    unit_cost: float

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class PORead(BaseModel):
    id: UUID
    supplier_id: UUID
    status: POStatus
    currency: str
    total_amount: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    lines: List[POLineRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
    
# ----- Receive -----
class POReceiveItem(BaseModel):
    line_id: UUID | str
    quantity: int = Field(..., gt=0)

class POReceivePayload(BaseModel):
    items: List[POReceiveItem]
    reason: Optional[str] = None
