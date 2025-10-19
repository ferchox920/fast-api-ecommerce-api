from __future__ import annotations

from celery import Celery
from kombu import Queue

from app.core.config import settings


celery_app = Celery("fastapi-ecommerce")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    broker_connection_retry_on_startup=True,
)

celery_app.conf.task_queues = (
    Queue(settings.CELERY_TASK_DEFAULT_QUEUE),
    Queue(settings.EMAIL_QUEUE),
    Queue(settings.REPORTS_QUEUE),
    Queue(settings.SCORING_QUEUE),
    Queue(settings.PROMOTION_EVENTS_QUEUE),
    Queue(settings.LOYALTY_EVENTS_QUEUE),
    Queue(settings.WISH_QUEUE),
)

celery_app.conf.task_routes = {
    "email.send_plain": {"queue": settings.EMAIL_QUEUE},
    "reports.generate_*": {"queue": settings.REPORTS_QUEUE},
    "scoring.run": {"queue": settings.SCORING_QUEUE},
    "events.promotion": {"queue": settings.PROMOTION_EVENTS_QUEUE},
    "events.loyalty": {"queue": settings.LOYALTY_EVENTS_QUEUE},
    "wish.evaluate": {"queue": settings.WISH_QUEUE},
}

celery_app.autodiscover_tasks(["app"])
