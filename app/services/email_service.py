# app/services/email_service.py
from app.core.celery_app import celery_app
from app.core.config import settings


def _enqueue_email(to_email: str, subject: str, body: str) -> None:
    task = celery_app.tasks.get("email.send_plain")
    if task is None:
        raise RuntimeError("Email task not registered")
    task.apply_async((to_email, subject, body), queue=settings.EMAIL_QUEUE, ignore_result=True)


def send_verification_email(to_email: str, verify_url: str) -> None:
    subject = f"{settings.PROJECT_NAME} - Verifica tu correo"
    body = f"Hola,\n\nVerifica tu correo haciendo clic en:\n{verify_url}\n\nSi no solicitaste esto, ignora el mensaje."
    _enqueue_email(to_email, subject, body)


def send_notification_email(to_email: str, subject: str, message: str) -> None:
    body = f"Hola,\n\n{message}\n\nGracias por usar {settings.PROJECT_NAME}."
    _enqueue_email(to_email, subject, body)
