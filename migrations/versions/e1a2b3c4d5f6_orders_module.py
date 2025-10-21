"""orders module (orders & order_lines)

Revision ID: e1a2b3c4d5f6
Revises: cd432b65bc61
Create Date: 2025-10-17 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "cd432b65bc61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUM robusto (no recrear si ya existe)
    orderstatus = postgresql.ENUM(
        "draft",
        "pending_payment",
        "paid",
        "fulfilled",
        "cancelled",
        "refunded",
        name="orderstatus",
        create_type=False,
    )
    orderstatus.create(op.get_bind(), checkfirst=True)

    # orders
    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),  # ← UUID para matchear users.id
        sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'ARS'")),
        sa.Column("status", orderstatus, nullable=False, server_default=sa.text("'draft'::orderstatus")),
        sa.Column("subtotal_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("shipping_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)

    # order_lines
    op.create_table(
        "order_lines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"], unique=False)

    # (Opcional) limpiar defaults tras backfill
    op.alter_column("orders", "currency", server_default=None)
    op.alter_column("orders", "status", server_default=None)
    op.alter_column("orders", "subtotal_amount", server_default=None)
    op.alter_column("orders", "discount_amount", server_default=None)
    op.alter_column("orders", "shipping_amount", server_default=None)
    op.alter_column("orders", "tax_amount", server_default=None)
    op.alter_column("orders", "total_amount", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_order_lines_order_id", table_name="order_lines")
    op.drop_table("order_lines")

    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")

    orderstatus = postgresql.ENUM(
        "draft",
        "pending_payment",
        "paid",
        "fulfilled",
        "cancelled",
        "refunded",
        name="orderstatus",
        create_type=False,
    )
    orderstatus.drop(op.get_bind(), checkfirst=True)
