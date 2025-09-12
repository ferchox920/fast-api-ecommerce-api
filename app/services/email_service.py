# app/services/email_service.py
import smtplib
from email.message import EmailMessage
from app.core.config import settings

def send_verification_email(to_email: str, verify_url: str) -> None:
    subject = f"{settings.PROJECT_NAME} - Verifica tu correo"
    body = f"Hola,\n\nVerifica tu correo haciendo clic en:\n{verify_url}\n\nSi no solicitaste esto, ignora el mensaje."

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
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
