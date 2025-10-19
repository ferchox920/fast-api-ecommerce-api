from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.report import (
    CostAnalysisReport,
    InventoryRotationReport,
    InventoryValueReport,
    SalesReport,
)
from app.services import report_service
from app.tasks import reports as report_tasks

router = APIRouter(prefix="/reports", tags=["reports"])


def _execute_task(async_result, schema_cls):
    data = async_result.get(timeout=settings.TASK_RESULT_TIMEOUT)
    return schema_cls(**data)


@router.get("/sales", response_model=SalesReport)
async def get_sales(
    days: int = Query(30, ge=1, le=365, description="Periodo del reporte en dias"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return await report_service.get_sales_report(db, days)
    async_result = report_tasks.generate_sales_report.delay(days=days)
    return _execute_task(async_result, SalesReport)


@router.get(
    "/inventory/value",
    response_model=InventoryValueReport,
    summary="Reporte de Valor de Inventario",
)
async def get_inventory_value(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return await report_service.get_inventory_value_report(db)
    async_result = report_tasks.generate_inventory_value_report.delay()
    return _execute_task(async_result, InventoryValueReport)


@router.get(
    "/purchases/cost-analysis",
    response_model=CostAnalysisReport,
    summary="Analisis de Costos de Compra",
)
async def get_cost_analysis(
    days: int = Query(30, ge=1, le=365, description="Periodo del reporte en dias"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return await report_service.get_cost_analysis_report(db, days)
    async_result = report_tasks.generate_cost_analysis_report.delay(days=days)
    return _execute_task(async_result, CostAnalysisReport)


@router.get(
    "/inventory/rotation",
    response_model=InventoryRotationReport,
    summary="Reporte de Rotacion de Inventario",
)
async def get_inventory_rotation(
    days: int = Query(30, ge=1, le=365, description="Periodo para calcular las ventas"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin", "purchases:read"]),
):
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return await report_service.get_inventory_rotation_report(db, days)
    async_result = report_tasks.generate_inventory_rotation_report.delay(days=days)
    return _execute_task(async_result, InventoryRotationReport)
