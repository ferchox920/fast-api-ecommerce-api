# app/services/email_delivery.py
import smtplib
from email.message import EmailMessage

from app.core.config import settings


def deliver_email(to_email: str, subject: str, body: str) -> None:
    if not settings.EMAILS_ENABLED or not settings.SMTP_HOST:
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
        except Exception as exc:  # pragma: no cover - fallback path
            print(f"[DEV EMAIL - FALLBACK] To: {to_email}\nSubject: {subject}\nError: {exc}\n---\n{body}\n")
