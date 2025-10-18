# app/services/email_service.py
import smtplib
from email.message import EmailMessage
from app.core.config import settings

def _send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.EMAILS_ENABLED or not settings.SMTP_HOST:
        # Modo dev: solo logueamos. Útil para Postman/testing.
        print(f"[DEV EMAIL] To: {to_email}\nSubject: {subject}\n---\n{body}\n")
        return

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_TLS:
            server.starttls()
        try:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        except Exception as exc:
            # Fallback to dev log when SMTP fails in non-production environments.
            print(f"[DEV EMAIL - FALLBACK] To: {to_email}\nSubject: {subject}\nError: {exc}\n---\n{body}\n")


def send_verification_email(to_email: str, verify_url: str) -> None:
    subject = f"{settings.PROJECT_NAME} - Verifica tu correo"
    body = f"Hola,\n\nVerifica tu correo haciendo clic en:\n{verify_url}\n\nSi no solicitaste esto, ignora el mensaje."
    _send_email(to_email, subject, body)


def send_notification_email(to_email: str, subject: str, message: str) -> None:
    body = f"Hola,\n\n{message}\n\nGracias por usar {settings.PROJECT_NAME}."
    _send_email(to_email, subject, body)
