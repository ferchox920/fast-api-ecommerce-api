# app/services/report_service.py
from datetime import datetime, timedelta, UTC
from sqlalchemy.orm import Session
from sqlalchemy import (
    func, select, text, and_, or_, column, cast, String
)

# Modelos y Schemas
from app.models.product import Product, ProductVariant
from app.models.purchase import PurchaseOrder, PurchaseOrderLine
from app.schemas.report import (
    SalesSummary, TopSeller, SalesReport,
    InventoryValueItem, InventoryValueReport,
    CostAnalysisItem, CostAnalysisReport,
    InventoryRotationItem, InventoryRotationReport
)

# ===== helpers para JOIN robusto por UUID =====
def _norm_uuid_sql(expr):
    """
    Normaliza un UUID a texto sin guiones y en minúsculas a nivel SQL,
    para que matchee tanto formatos con guiones (canonical) como hex plano.
    """
    return func.replace(func.lower(cast(expr, String)), "-", "")


# =========================
# Reporte de Ventas
# =========================
def get_sales_report(db: Session, days: int = 30) -> SalesReport:
    now_utc = datetime.now(UTC)
    start_date = now_utc - timedelta(days=days)
    start_date_iso = start_date.isoformat(timespec="seconds")

    # columnas tipadas para la tabla textual
    vcol = column("variant_id", String)
    qcol = column("quantity")

    sales_stmt = (
        select(
            vcol.label("variant_id"),
            func.sum(qcol).label("units_sold"),
        )
        .select_from(text("inventory_movements"))
        .where(
            text("type = 'sale'"),
            text("created_at >= :start_date"),
        )
        .group_by(vcol)
        .cte("sales_data")
    )

    # condición de join tolerante a distintos formatos de UUID
    join_cond = or_(
        cast(ProductVariant.id, String) == cast(sales_stmt.c.variant_id, String),
        _norm_uuid_sql(ProductVariant.id) == _norm_uuid_sql(sales_stmt.c.variant_id),
    )

    stmt = (
        select(
            Product.id.label("product_id"),
            Product.title.label("product_title"),
            ProductVariant.sku,
            sales_stmt.c.units_sold,
            (sales_stmt.c.units_sold * Product.price).label("estimated_revenue"),
        )
        .join(ProductVariant, Product.id == ProductVariant.product_id)
        .join(sales_stmt, join_cond)
        .order_by(sales_stmt.c.units_sold.desc())
    )

    rows = db.execute(stmt, {"start_date": start_date_iso}).mappings().all()
    top_sellers = [
        TopSeller(
            product_id=row["product_id"],
            product_title=row["product_title"],
            sku=row["sku"],
            units_sold=int(row["units_sold"]),
            estimated_revenue=float(row["estimated_revenue"] or 0.0),
        )
        for row in rows
    ]

    total_revenue = sum(ts.estimated_revenue for ts in top_sellers)
    total_units_sold = sum(ts.units_sold for ts in top_sellers)

    total_sales_transactions = (
        db.execute(
            select(func.count())
            .select_from(text("inventory_movements"))
            .where(text("type = 'sale'"), text("created_at >= :start_date")),
            {"start_date": start_date_iso},
        ).scalar_one_or_none()
        or 0
    )

    sales_summary = SalesSummary(
        total_revenue=total_revenue,
        total_sales_transactions=int(total_sales_transactions),
        total_units_sold=int(total_units_sold),
    )
    return SalesReport(
        generated_at=now_utc,
        period_days=days,
        sales_summary=sales_summary,
        top_sellers=top_sellers,
    )


# =========================
# Valor de Inventario
# =========================
def get_inventory_value_report(db: Session) -> InventoryValueReport:
    """
    Calcula el valor estimado del inventario actual multiplicando
    stock_on_hand por el último costo recibido.
    """
    now_utc = datetime.now(UTC)

    last_cost_subq = (
        select(
            PurchaseOrderLine.variant_id,
            PurchaseOrderLine.unit_cost,
            func.row_number()
            .over(
                partition_by=PurchaseOrderLine.variant_id,
                order_by=PurchaseOrder.created_at.desc(),
            )
            .label("rn"),
        )
        .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .subquery("last_cost_sub")
    )

    stmt = (
        select(
            ProductVariant.id.label("variant_id"),
            ProductVariant.sku,
            Product.title.label("product_title"),
            ProductVariant.stock_on_hand,
            last_cost_subq.c.unit_cost.label("last_unit_cost"),
        )
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(
            last_cost_subq,
            and_(
                ProductVariant.id == last_cost_subq.c.variant_id,
                last_cost_subq.c.rn == 1,
            ),
        )
        .where(ProductVariant.stock_on_hand > 0)
        .order_by(Product.title)
    )

    rows = db.execute(stmt).mappings().all()

    items = []
    total_value = 0.0
    total_units = 0

    for r in rows:
        on_hand = int(r["stock_on_hand"])
        cost = float(r["last_unit_cost"] or 0.0)
        value = on_hand * cost

        items.append(
            InventoryValueItem(
                variant_id=r["variant_id"],
                sku=r["sku"],
                product_title=r["product_title"],
                stock_on_hand=on_hand,
                last_unit_cost=cost,
                estimated_value=value,
            )
        )
        total_value += value
        total_units += on_hand

    return InventoryValueReport(
        generated_at=now_utc,
        total_estimated_value=total_value,
        total_units=total_units,
        items=items,
    )


# =========================
# Análisis de Costos (Compras)
# =========================
def get_cost_analysis_report(db: Session, days: int = 30) -> CostAnalysisReport:
    now_utc = datetime.now(UTC)
    start_date = now_utc - timedelta(days=days)

    stmt = (
        select(
            Product.id.label("product_id"),
            ProductVariant.id.label("variant_id"),
            ProductVariant.sku,
            Product.title.label("product_title"),
            func.sum(PurchaseOrderLine.qty_received).label("units_purchased"),
            func.sum(
                PurchaseOrderLine.qty_received * PurchaseOrderLine.unit_cost
            ).label("total_cost"),
        )
        .join(ProductVariant, PurchaseOrderLine.variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.created_at >= start_date,
            PurchaseOrderLine.qty_received > 0,
        )
        .group_by(Product.id, ProductVariant.id)
        .order_by(
            func.sum(
                PurchaseOrderLine.qty_received * PurchaseOrderLine.unit_cost
            ).desc()
        )
    )

    rows = db.execute(stmt).mappings().all()

    items = []
    for r in rows:
        units = int(r["units_purchased"] or 0)
        total_cost = float(r["total_cost"] or 0.0)
        avg = (total_cost / units) if units else 0.0

        items.append(
            CostAnalysisItem(
                product_id=r["product_id"],
                variant_id=r["variant_id"],
                sku=r["sku"],
                product_title=r["product_title"],
                units_purchased=units,
                total_cost=total_cost,
                average_cost=avg,
            )
        )

    return CostAnalysisReport(
        generated_at=now_utc,
        period_days=days,
        total_units_purchased=sum(i.units_purchased for i in items),
        total_purchase_cost=sum(i.total_cost for i in items),
        items_by_product=items,
    )


# =========================
# Rotación de Inventario
# =========================
def get_inventory_rotation_report(db: Session, days: int = 30) -> InventoryRotationReport:
    """
    Calcula la rotación de inventario para identificar productos de movimiento lento.
    """
    now_utc = datetime.now(UTC)
    start_date = now_utc - timedelta(days=days)
    start_date_iso = start_date.isoformat(timespec="seconds")

    # columnas tipadas para la tabla textual
    vcol = column("variant_id", String)
    qcol = column("quantity")

    sales_in_period = (
        select(
            vcol.label("variant_id"),
            func.sum(qcol).label("units_sold"),
        )
        .select_from(text("inventory_movements"))
        .where(
            text("type = 'sale'"),
            text("created_at >= :start_date"),
        )
        .group_by(vcol)
        .cte("sales_in_period")
    )

    # condición de join robusta
    join_cond = or_(
        cast(ProductVariant.id, String) == cast(sales_in_period.c.variant_id, String),
        _norm_uuid_sql(ProductVariant.id) == _norm_uuid_sql(sales_in_period.c.variant_id),
    )

    stmt = select(
        Product.id.label("product_id"),
        ProductVariant.id.label("variant_id"),
        ProductVariant.sku,
        Product.title.label("product_title"),
        ProductVariant.stock_on_hand.label("current_stock"),
        func.coalesce(sales_in_period.c.units_sold, 0).label("units_sold"),
    ).select_from(ProductVariant)

    stmt = stmt.join(Product, ProductVariant.product_id == Product.id)
    stmt = stmt.outerjoin(sales_in_period, join_cond)
    stmt = stmt.order_by(
        func.coalesce(sales_in_period.c.units_sold, 0).asc(),
        ProductVariant.stock_on_hand.desc(),
    )

    rows = db.execute(stmt, {"start_date": start_date_iso}).mappings().all()

    items = []
    for r in rows:
        current_stock = int(r["current_stock"] or 0)
        units_sold = int(r["units_sold"] or 0)
        turnover_ratio = (units_sold / current_stock) if current_stock > 0 else 0.0

        items.append(
            InventoryRotationItem(
                product_id=r["product_id"],
                variant_id=r["variant_id"],
                sku=r["sku"],
                product_title=r["product_title"],
                units_sold=units_sold,
                current_stock=current_stock,
                turnover_ratio=turnover_ratio,
            )
        )

    return InventoryRotationReport(
        generated_at=now_utc,
        period_days=days,
        items=items,
    )


__all__ = [
    "get_sales_report",
    "get_inventory_value_report",
    "get_cost_analysis_report",
    "get_inventory_rotation_report",
]
