# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict, HttpUrl
from typing import Optional, List

class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None

    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None

    birthdate: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    avatar_url: HttpUrl | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserCreateOAuth(BaseModel):
    email: EmailStr
    full_name: str | None = None
    oauth_provider: str
    oauth_sub: str
    oauth_picture: HttpUrl | None = None
    email_verified_from_provider: bool | None = None  # ej: claim de Google


class UserUpdate(BaseModel):
    full_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None
    birthdate: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    avatar_url: HttpUrl | None = None


class UserRead(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    email_verified: bool

    oauth_provider: str | None = None
    oauth_sub: str | None = None
    oauth_picture: HttpUrl | None = None

    # Pydantic v2
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: Optional[int] = None
    type: Optional[str] = None                 # "access" | "refresh" | "verify_email"
    scopes: Optional[List[str]] = None         # scopes opcionales

    # Permitir campos extra para compatibilidad futura
    model_config = ConfigDict(extra="allow")
