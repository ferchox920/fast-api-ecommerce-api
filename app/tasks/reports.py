from __future__ import annotations

import asyncio

from app.core.celery_app import celery_app
from app.db.session_async import AsyncSessionLocal
from app.services import report_service


async def _run_async(func, *args, **kwargs):
    async with AsyncSessionLocal() as session:
        return await func(session, *args, **kwargs)


def _run(func, *args, **kwargs):
    return asyncio.run(_run_async(func, *args, **kwargs))


@celery_app.task(name="reports.generate_sales_report")
def generate_sales_report(days: int = 30) -> dict:
    report = _run(report_service.get_sales_report, days=days)
    return report.model_dump()


@celery_app.task(name="reports.generate_inventory_value_report")
def generate_inventory_value_report() -> dict:
    report = _run(report_service.get_inventory_value_report)
    return report.model_dump()


@celery_app.task(name="reports.generate_cost_analysis_report")
def generate_cost_analysis_report(days: int = 30) -> dict:
    report = _run(report_service.get_cost_analysis_report, days=days)
    return report.model_dump()


@celery_app.task(name="reports.generate_inventory_rotation_report")
def generate_inventory_rotation_report(days: int = 30) -> dict:
    report = _run(report_service.get_inventory_rotation_report, days=days)
    return report.model_dump()
