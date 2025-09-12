# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserRead

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    expires_in: int
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenRefresh(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer")
    expires_in: int


class VerifyEmailRequest(BaseModel):
    email: EmailStr  # Más estricto que str para validación automática
