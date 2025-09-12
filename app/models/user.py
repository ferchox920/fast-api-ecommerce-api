# app/models/user.py
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, func, Index
from uuid import uuid4
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)  # None si es sólo OAuth
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Verificación de email
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at = mapped_column(DateTime(timezone=True), nullable=True)

    # Dirección (flat)
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city:          Mapped[str | None] = mapped_column(String(120), nullable=True)
    state:         Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code:   Mapped[str | None] = mapped_column(String(30), nullable=True)
    country:       Mapped[str | None] = mapped_column(String(2), nullable=True)
    phone:         Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Extras
    birthdate:     Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD simple
    avatar_url:    Mapped[str | None] = mapped_column(String(512), nullable=True)

    # OAuth
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)   # "google", "github", ...
    oauth_sub:      Mapped[str | None] = mapped_column(String(255), nullable=True)  # subject del IdP
    oauth_picture:  Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Auditoría
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), onupdate=func.now())

Index("ix_user_oauth_provider_sub", User.oauth_provider, User.oauth_sub, unique=False)
