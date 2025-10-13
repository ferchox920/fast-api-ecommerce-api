# app/api/routers/reports.py
from fastapi import APIRouter, Depends, Security, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.report import ReportRead
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/sales", response_model=ReportRead)
def get_sales_report(
    days: int = Query(30, ge=1, le=365, description="Período del reporte en días"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    """
    Obtiene un reporte consolidado de ventas y productos más vendidos
    basado en los movimientos de inventario de tipo 'sale'.

    Requiere permisos de administrador o de lectura de compras.
    """
    return report_service.get_sales_report(db, days=days)