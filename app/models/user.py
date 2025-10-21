# app/models/user.py
from __future__ import annotations

import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import TypeDecorator
from app.db.session import Base


class GUID(TypeDecorator):
    """Tipo UUID portable.
    - En PostgreSQL usa UUID nativo (as_uuid=True)
    - En SQLite/otros usa String(36)
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name != "postgresql" else value
        # si viene como str, normalizamos
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        # devolvemos siempre uuid.UUID en Python
        return uuid.UUID(str(value))


class User(Base):
    __tablename__ = "users"

    # Generamos el UUID en Python para que funcione en SQLite y Postgres.
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,      # 👈 genera en app (compatible con SQLite)
        nullable=False,
    )

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
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    oauth_sub:      Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_picture:  Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Auditoría
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_user_oauth_provider_sub", "oauth_provider", "oauth_sub", unique=False),
    )
