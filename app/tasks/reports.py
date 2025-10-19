from __future__ import annotations

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services import report_service


def _run_with_session(func, *args, **kwargs):
    db = SessionLocal()
    try:
        result = func(db, *args, **kwargs)
    finally:
        db.close()
    return result


@celery_app.task(name="reports.generate_sales_report")
def generate_sales_report(days: int = 30) -> dict:
    report = _run_with_session(report_service.get_sales_report, days=days)
    return report.model_dump()


@celery_app.task(name="reports.generate_inventory_value_report")
def generate_inventory_value_report() -> dict:
    report = _run_with_session(report_service.get_inventory_value_report)
    return report.model_dump()


@celery_app.task(name="reports.generate_cost_analysis_report")
def generate_cost_analysis_report(days: int = 30) -> dict:
    report = _run_with_session(report_service.get_cost_analysis_report, days=days)
    return report.model_dump()


@celery_app.task(name="reports.generate_inventory_rotation_report")
def generate_inventory_rotation_report(days: int = 30) -> dict:
    report = _run_with_session(report_service.get_inventory_rotation_report, days=days)
    return report.model_dump()
