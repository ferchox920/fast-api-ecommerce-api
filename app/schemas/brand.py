from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

# ---------- Brand ----------
class BrandBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    # el modelo usa slug hasta 140 chars
    slug: str | None = Field(None, min_length=2, max_length=140)
    description: str | None = Field(None, max_length=500)
    active: bool = True


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    slug: str | None = Field(None, min_length=2, max_length=140)
    description: str | None = Field(None, max_length=500)
    active: bool | None = None


class BrandRead(BrandBase):
    id: UUID  # usar UUID; Pydantic lo serializa a string en JSON
    model_config = ConfigDict(from_attributes=True)
