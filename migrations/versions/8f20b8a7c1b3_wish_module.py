"""wish module

Revision ID: 8f20b8a7c1b3
Revises: cd432b65bc61
Create Date: 2025-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8f20b8a7c1b3"
down_revision: Union[str, Sequence[str], None] = "cd432b65bc61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wishes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("desired_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notify_discount", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.Enum("active", "fulfilled", "cancelled", name="wish_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wishes_user_id", "wishes", ["user_id"], unique=False)
    op.create_index("ix_wishes_user_product", "wishes", ["user_id", "product_id"], unique=True)

    op.create_table(
        "wish_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["wish_id"],
            ["wishes.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wish_notifications_wish_id", "wish_notifications", ["wish_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wish_notifications_wish_id", table_name="wish_notifications")
    op.drop_table("wish_notifications")
    op.drop_index("ix_wishes_user_product", table_name="wishes")
    op.drop_index("ix_wishes_user_id", table_name="wishes")
    op.drop_table("wishes")
    sa.Enum(name="wish_status").drop(op.get_bind(), checkfirst=False)
