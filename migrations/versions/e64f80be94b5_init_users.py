"""init users

Revision ID: e64f80be94b5
Revises:
Create Date: 2025-10-21 17:04:05.059955
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e64f80be94b5"
down_revision: Union[str, Sequence[str], None] = None  # ← raíz, sin dependencias
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensiones útiles para UUID por función gen_random_uuid()
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto;')

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    # Índice opcional (ya es unique, pero si querés index adicional):
    # op.create_index('ix_users_email', 'users', ['email'], unique=True)


def downgrade() -> None:
    # Si creaste índices extra, eliminarlos antes
    # op.drop_index('ix_users_email', table_name='users')
    op.drop_table("users")
