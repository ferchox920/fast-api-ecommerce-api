# app/api/routers/reports.py
from fastapi import APIRouter, Depends, Security, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.report import (
    SalesReport,
    InventoryValueReport,
    CostAnalysisReport,
    InventoryRotationReport,
)

# Importar funciones directamente (evita ambigüedades en resolución de módulos)
from app.services.report_service import (
    get_sales_report as svc_get_sales_report,
    get_inventory_value_report as svc_get_inventory_value_report,
    get_cost_analysis_report as svc_get_cost_analysis_report,
    get_inventory_rotation_report as svc_get_inventory_rotation_report,
)

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/sales", response_model=SalesReport)
def get_sales(
    days: int = Query(30, ge=1, le=365, description="Período del reporte en días"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    """Obtiene un reporte consolidado de ventas y productos más vendidos."""
    return svc_get_sales_report(db, days=days)


@router.get(
    "/inventory/value",
    response_model=InventoryValueReport,
    summary="Reporte de Valor de Inventario",
)
def get_inventory_value(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    """
    Estima el valor total del inventario actual multiplicando el stock disponible
    de cada variante por su último costo de compra registrado.
    """
    return svc_get_inventory_value_report(db)


@router.get(
    "/purchases/cost-analysis",
    response_model=CostAnalysisReport,
    summary="Análisis de Costos de Compra",
)
def get_cost_analysis(
    days: int = Query(30, ge=1, le=365, description="Período del reporte en días"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    """
    Analiza los costos de los productos comprados (stock recibido) en un
    período de tiempo determinado, agrupado por variante.
    """
    return svc_get_cost_analysis_report(db, days=days)


@router.get(
    "/inventory/rotation",
    response_model=InventoryRotationReport,
    summary="Reporte de Rotación de Inventario",
)
def get_inventory_rotation(
    days: int = Query(30, ge=1, le=365, description="Período para calcular las ventas"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    """
    Genera un reporte de rotación para identificar productos de bajo movimiento.
    Compara las unidades vendidas en un período contra el stock actual.
    """
    return svc_get_inventory_rotation_report(db, days=days)
