"""orders module (orders & order_lines)

Revision ID: e1a2b3c4d5f6
Revises: cd432b65bc61
Create Date: 2025-10-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "cd432b65bc61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ARS"),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_payment",
                "paid",
                "fulfilled",
                "cancelled",
                "refunded",
                name="orderstatus",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("subtotal_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("shipping_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"], unique=False)

    op.create_table(
        "order_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # limpiar server_default de campos monetarios y currency/status tras backfill si se desea
    op.alter_column("orders", "currency", server_default=None)
    op.alter_column("orders", "status", server_default=None)
    op.alter_column("orders", "subtotal_amount", server_default=None)
    op.alter_column("orders", "discount_amount", server_default=None)
    op.alter_column("orders", "shipping_amount", server_default=None)
    op.alter_column("orders", "tax_amount", server_default=None)
    op.alter_column("orders", "total_amount", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("order_lines")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")

