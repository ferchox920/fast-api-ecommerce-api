"""cart module

Revision ID: f1234567890ab
Revises: e1a2b3c4d5f6
Create Date: 2025-10-17 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1234567890ab"
down_revision: Union[str, Sequence[str], None] = "e1a2b3c4d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "carts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("guest_token", sa.String(length=120), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "converted", "abandoned", name="cartstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="ARS"),
        sa.Column("subtotal_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guest_token", name="uq_carts_guest_token"),
    )
    op.create_index("ix_carts_user_id", "carts", ["user_id"], unique=False)
    op.create_index("ix_carts_guest_token", "carts", ["guest_token"], unique=False)

    op.create_table(
        "cart_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cart_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", "variant_id", name="uq_cart_items_cart_variant"),
    )

    op.alter_column("carts", "status", server_default=None)
    op.alter_column("carts", "currency", server_default=None)
    op.alter_column("carts", "subtotal_amount", server_default=None)
    op.alter_column("carts", "discount_amount", server_default=None)
    op.alter_column("carts", "total_amount", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("cart_items")
    op.drop_index("ix_carts_guest_token", table_name="carts")
    op.drop_index("ix_carts_user_id", table_name="carts")
    op.drop_table("carts")
