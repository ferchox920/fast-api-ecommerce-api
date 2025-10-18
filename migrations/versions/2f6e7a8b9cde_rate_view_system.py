"""rate view system foundations

Revision ID: 2f6e7a8b9cde
Revises: 1abc2def3ghi
Create Date: 2025-10-17 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2f6e7a8b9cde"
down_revision: Union[str, Sequence[str], None] = "1abc2def3ghi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'promotion'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'loyalty'")

    op.create_table(
        "product_engagement_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("carts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "date", name="uq_product_engagement_daily_product_date"),
    )
    op.create_index("ix_product_engagement_daily_date", "product_engagement_daily", ["date"])

    op.create_table(
        "customer_engagement_daily",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("carts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "date", name="uq_customer_engagement_daily_user_date"),
    )
    op.create_index("ix_customer_engagement_daily_date", "customer_engagement_daily", ["date"])

    op.create_table(
        "product_rankings",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("popularity_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("cold_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("profit_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("freshness_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("exposure_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index("ix_product_rankings_updated_at", "product_rankings", ["updated_at"])

    op.create_table(
        "exposure_slots",
        sa.Column("slot_id", sa.UUID(), nullable=False),
        sa.Column("context", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("slot_id"),
        sa.UniqueConstraint("context", "user_id", name="uq_exposure_slots_context_user"),
    )
    op.create_index("ix_exposure_slots_expires_at", "exposure_slots", ["expires_at"])

    promotion_type = sa.Enum("category", "product", "customer", name="promotiontype")
    status_enum = sa.Enum("draft", "active", "scheduled", "expired", name="promotionstatus")

    promotion_type.create(op.get_bind(), checkfirst=True)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "promotions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", promotion_type, nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False, server_default="global"),
        sa.Column("criteria_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("benefits_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promotions_status", "promotions", ["status"])
    op.create_index("ix_promotions_start_end", "promotions", ["start_at", "end_at"])
    # INTEGRATION: 'criteria_json' y 'benefits_json' se coordinarán con el motor de pricing/checkout.

    op.create_table(
        "promotion_products",
        sa.Column("promotion_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("promotion_id", "product_id"),
    )

    op.create_table(
        "promotion_customers",
        sa.Column("promotion_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("promotion_id", "customer_id"),
    )

    op.create_table(
        "loyalty_levels",
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("min_points", sa.Integer(), nullable=False),
        sa.Column("perks_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("level"),
    )

    op.create_table(
        "loyalty_profile",
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["level"], ["loyalty_levels.level"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("customer_id"),
    )
    op.create_index("ix_loyalty_profile_level", "loyalty_profile", ["level"])
    # INTEGRATION: 'progress_json' compatibiliza con futuras misiones/retos (gamificación).

    op.create_table(
        "loyalty_history",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("level", sa.String(length=50), nullable=False),
        sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("loyalty_history")
    op.drop_index("ix_loyalty_profile_level", table_name="loyalty_profile")
    op.drop_table("loyalty_profile")
    op.drop_table("loyalty_levels")
    op.drop_table("promotion_customers")
    op.drop_table("promotion_products")
    op.drop_index("ix_promotions_start_end", table_name="promotions")
    op.drop_index("ix_promotions_status", table_name="promotions")
    op.drop_table("promotions")
    op.drop_index("ix_exposure_slots_expires_at", table_name="exposure_slots")
    op.drop_table("exposure_slots")
    op.drop_index("ix_product_rankings_updated_at", table_name="product_rankings")
    op.drop_table("product_rankings")
    op.drop_index("ix_customer_engagement_daily_date", table_name="customer_engagement_daily")
    op.drop_table("customer_engagement_daily")
    op.drop_index("ix_product_engagement_daily_date", table_name="product_engagement_daily")
    op.drop_table("product_engagement_daily")
    op.execute("DROP TYPE IF EXISTS promotiontype")
    op.execute("DROP TYPE IF EXISTS promotionstatus")
