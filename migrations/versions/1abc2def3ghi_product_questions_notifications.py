"""product questions and notifications

Revision ID: 1abc2def3ghi
Revises: 0a1b2c3d4e5f
Create Date: 2025-10-17 02:36:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1abc2def3ghi"
down_revision: Union[str, Sequence[str], None] = "0a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────────
    # Crear tipos ENUM solo si no existen (evita DuplicateObject)
    # ──────────────────────────────────────────────────────────────────────
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'questionstatus'
        ) THEN
            CREATE TYPE questionstatus AS ENUM ('pending','answered','hidden','blocked');
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typname = 'notificationtype'
        ) THEN
            CREATE TYPE notificationtype AS ENUM ('product_question','product_answer','order_status','new_order','generic');
        END IF;
    END $$;
    """)

    question_status_enum = postgresql.ENUM(name="questionstatus", create_type=False)
    notification_type_enum = postgresql.ENUM(name="notificationtype", create_type=False)

    # ──────────────────────────────────────────────────────────────────────
    # Tablas
    # ──────────────────────────────────────────────────────────────────────
    op.create_table(
        "product_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            question_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::questionstatus"),
        ),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_product_questions_product", "product_questions", ["product_id"], unique=False)
    op.create_index("ix_product_questions_user", "product_questions", ["user_id"], unique=False)
    op.create_index("ix_product_questions_status", "product_questions", ["status"], unique=False)

    op.create_table(
        "product_answers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["question_id"], ["product_questions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_product_answers_question", "product_answers", ["question_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", notification_type_enum, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)

    # Limpiar defaults si no querés mantenerlos en el esquema
    op.alter_column("product_questions", "status", server_default=None)
    op.alter_column("notifications", "is_read", server_default=None)


def downgrade() -> None:
    # Notas: borrar en orden inverso de dependencias
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_user", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_product_answers_question", table_name="product_answers")
    op.drop_table("product_answers")

    op.drop_index("ix_product_questions_status", table_name="product_questions")
    op.drop_index("ix_product_questions_user", table_name="product_questions")
    op.drop_index("ix_product_questions_product", table_name="product_questions")
    op.drop_table("product_questions")

    bind = op.get_bind()
    postgresql.ENUM(name="notificationtype").drop(bind, checkfirst=True)
    postgresql.ENUM(name="questionstatus").drop(bind, checkfirst=True)
