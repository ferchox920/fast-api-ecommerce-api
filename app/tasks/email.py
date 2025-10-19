from __future__ import annotations

from app.core.celery_app import celery_app
from app.services.email_delivery import deliver_email


@celery_app.task(name="email.send_plain", bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to_email: str, subject: str, body: str) -> None:
    """Send an email message asynchronously."""
    try:
        deliver_email(to_email, subject, body)
    except Exception as exc:  # pragma: no cover - retries handled by Celery
        raise self.retry(exc=exc)
