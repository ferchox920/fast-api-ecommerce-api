# app/services/report_service.py
from sqlalchemy.orm import Session
from sqlalchemy import func, select, text
from datetime import datetime, timedelta

from app.models.product import Product, ProductVariant
from app.schemas.report import SalesSummary, TopSeller, ReportRead

def get_sales_report(db: Session, days: int = 30) -> ReportRead:
    """
    Genera un reporte de ventas consolidado basándose en los movimientos
    de inventario de tipo 'sale'.
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Subconsulta para obtener los movimientos de venta en el período
    sales_stmt = select(
        text("variant_id"),
        func.sum(text("quantity")).label("units_sold")
    ).where(
        text("type = 'sale'"),
        text(f"created_at >= '{start_date}'")
    ).group_by(
        text("variant_id")
    ).cte("sales_data")

    # Consulta principal que une los resultados con productos y variantes
    stmt = select(
        Product.id.label("product_id"),
        Product.title.label("product_title"),
        ProductVariant.sku,
        sales_stmt.c.units_sold,
        (sales_stmt.c.units_sold * func.coalesce(ProductVariant.price_override, Product.price)).label("estimated_revenue")
    ).join(
        ProductVariant, Product.id == ProductVariant.product_id
    ).join(
        sales_stmt, ProductVariant.id == sales_stmt.c.variant_id
    ).order_by(
        sales_stmt.c.units_sold.desc()
    )

    results = db.execute(stmt).all()

    # Procesar para los schemas
    top_sellers = [TopSeller(**row._asdict()) for row in results]

    # Calcular el resumen
    total_revenue = sum(seller.estimated_revenue for seller in top_sellers)
    total_units_sold = sum(seller.units_sold for seller in top_sellers)

    # Para total_sales_transactions, necesitamos otra consulta (o podemos estimarlo)
    # Por ahora, contaremos los registros de venta distintos.
    total_sales_transactions = db.execute(
        select(func.count())
        .where(text("type = 'sale'"), text(f"created_at >= '{start_date}'"))
    ).scalar_one_or_none() or 0

    sales_summary = SalesSummary(
        total_revenue=total_revenue,
        total_sales_transactions=total_sales_transactions,
        total_units_sold=total_units_sold
    )

    return ReportRead(
        generated_at=datetime.utcnow(),
        period_days=days,
        sales_summary=sales_summary,
        top_sellers=top_sellers,
    )