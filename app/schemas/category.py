# app/schemas/category.py
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime

# ---------- Category ----------
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=500)
    active: bool = True

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    slug: str | None = Field(None, min_length=2, max_length=120)
    description: str | None = Field(None, max_length=500)
    active: bool | None = None

class CategoryRead(CategoryBase):
    id: UUID  # mantiene UUID
    created_at: datetime  # para debug/ordenamiento
    model_config = ConfigDict(from_attributes=True)
