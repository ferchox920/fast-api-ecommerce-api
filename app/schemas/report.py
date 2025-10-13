# app/schemas/report.py
from pydantic import BaseModel, Field
from typing import List
from uuid import UUID
from datetime import datetime

class SalesSummary(BaseModel):
    total_revenue: float = Field(..., description="Ingresos totales estimados en el período")
    total_sales_transactions: int = Field(..., description="Número de transacciones de venta registradas")
    total_units_sold: int = Field(..., description="Cantidad total de unidades de productos vendidos")

class TopSeller(BaseModel):
    product_id: UUID
    product_title: str
    sku: str
    units_sold: int
    estimated_revenue: float

class ReportRead(BaseModel):
    generated_at: datetime
    period_days: int = 30
    sales_summary: SalesSummary
    top_sellers: List[TopSeller]