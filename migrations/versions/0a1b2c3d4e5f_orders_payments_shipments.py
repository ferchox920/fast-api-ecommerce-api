"""orders payments shipments enhancements

Revision ID: 0a1b2c3d4e5f
Revises: f1234567890ab
Create Date: 2025-10-17 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "f1234567890ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    payment_status_enum = sa.Enum(
        "pending",
        "authorized",
        "approved",
        "rejected",
        "cancelled",
        "refunded",
        name="paymentstatus",
    )
    shipping_status_enum = sa.Enum(
        "pending",
        "preparing",
        "shipped",
        "delivered",
        "returned",
        name="shippingstatus",
    )

    payment_status_enum.create(op.get_bind(), checkfirst=True)
    shipping_status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "orders",
        sa.Column("payment_status", payment_status_enum, server_default="pending", nullable=False),
    )
    op.add_column(
        "orders",
        sa.Column("shipping_status", shipping_status_enum, server_default="pending", nullable=False),
    )
    op.add_column("orders", sa.Column("shipping_address", sa.JSON(), nullable=True))
    op.add_column("orders", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_orders_status", "orders", ["status"])  # type: ignore[arg-type]
    op.create_index("ix_orders_payment_status", "orders", ["payment_status"])
    op.create_index("ix_orders_shipping_status", "orders", ["shipping_status"])

    provider_enum = sa.Enum("mercado_pago", name="paymentprovider")
    provider_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("provider", provider_enum, nullable=False),
        sa.Column("provider_payment_id", sa.String(length=140), nullable=True),
        sa.Column("status", payment_status_enum, nullable=False, server_default="pending"),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("init_point", sa.String(length=500), nullable=True),
        sa.Column("sandbox_init_point", sa.String(length=500), nullable=True),
        sa.Column("raw_preference", sa.JSON(), nullable=True),
        sa.Column("last_webhook", sa.JSON(), nullable=True),
        sa.Column("status_detail", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "shipments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("status", shipping_status_enum, nullable=False, server_default="pending"),
        sa.Column("carrier", sa.String(length=120), nullable=True),
        sa.Column("tracking_number", sa.String(length=140), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.alter_column("orders", "payment_status", server_default=None)
    op.alter_column("orders", "shipping_status", server_default=None)
    op.alter_column("payments", "status", server_default=None)
    op.alter_column("shipments", "status", server_default=None)


def downgrade() -> None:
    op.drop_table("shipments")
    op.drop_table("payments")
    op.drop_index("ix_orders_shipping_status", table_name="orders")
    op.drop_index("ix_orders_payment_status", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")

    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "fulfilled_at")
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "notes")
    op.drop_column("orders", "shipping_address")
    op.drop_column("orders", "shipping_status")
    op.drop_column("orders", "payment_status")

    op.execute("DROP TYPE IF EXISTS paymentprovider")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS shippingstatus")
