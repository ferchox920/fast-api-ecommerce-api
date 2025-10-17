# app/schemas/report.py
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# --- Reporte de Ventas (Estructura base existente) ---
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

class SalesReport(BaseModel):
    generated_at: datetime
    period_days: int = 30
    sales_summary: SalesSummary
    top_sellers: List[TopSeller]


# --- NUEVO: Reporte de Valor de Inventario ---
class InventoryValueItem(BaseModel):
    variant_id: UUID
    sku: str
    product_title: str
    stock_on_hand: int
    last_unit_cost: Optional[float] = Field(None, description="Último costo de compra registrado")
    estimated_value: float = Field(description="stock_on_hand * last_unit_cost")

class InventoryValueReport(BaseModel):
    generated_at: datetime
    total_estimated_value: float
    total_units: int
    items: List[InventoryValueItem]


# --- NUEVO: Reporte de Análisis de Costos ---
class CostAnalysisItem(BaseModel):
    product_id: UUID
    variant_id: UUID
    sku: str
    product_title: str
    units_purchased: int
    total_cost: float
    average_cost: float

class CostAnalysisReport(BaseModel):
    generated_at: datetime
    period_days: int
    total_units_purchased: int
    total_purchase_cost: float
    items_by_product: List[CostAnalysisItem]


# --- NUEVO: Reporte de Rotación de Inventario ---
class InventoryRotationItem(BaseModel):
    product_id: UUID
    variant_id: UUID
    sku: str
    product_title: str
    units_sold: int
    current_stock: int
    turnover_ratio: Optional[float] = Field(None, description="Ratio simple: Unidades vendidas / Stock actual. Un valor nulo indica 0 stock.")

class InventoryRotationReport(BaseModel):
    generated_at: datetime
    period_days: int
    notes: str = "La rotación se calcula como unidades vendidas en el período dividido por el stock actual. Interpretar con cuidado."
    items: List[InventoryRotationItem]