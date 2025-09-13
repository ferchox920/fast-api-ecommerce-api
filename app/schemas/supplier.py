from pydantic import BaseModel, Field
from pydantic import ConfigDict
from uuid import UUID
from typing import Optional

class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None

class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    email: Optional[str] = None
    phone: Optional[str] = None

class SupplierRead(BaseModel):
    id: UUID                # <-- UUID, no str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
