import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config.env_config import ENV_CONFIG
from src.utils.email_templates import (
    verification_email_template,
    new_application_notification_template,
    application_status_update_template,
    shortlist_notification_template,
)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587
_FROM_NAME = "ResumeEZ"


def _send_email_sync(to: str, subject: str, html: str) -> None:
    """Blocking SMTP send — called via run_in_executor so it never blocks the event loop."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{_FROM_NAME} <{ENV_CONFIG.APP_EMAIL}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(ENV_CONFIG.APP_EMAIL, ENV_CONFIG.APP_PASS)
        server.sendmail(ENV_CONFIG.APP_EMAIL, to, msg.as_string())


async def _send_email(to: str, subject: str, html: str) -> None:
    """Async wrapper — fire and forget, swallows errors so the pipeline is never blocked."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_email_sync, to, subject, html)
    except Exception as e:
        print(f"[EMAIL] Failed to send to {to}: {e}")


async def send_verification_email(email: str, token: str) -> None:
    """Send account verification email — raises on failure (intentional, used during signup)."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _send_email_sync,
        email,
        "Verify your ResumeEZ account",
        verification_email_template(token),
    )


async def send_new_application_notification(
    recruiter_email: str,
    candidate_name: str,
    job_title: str,
    applied_at: str,
) -> None:
    await _send_email(
        to=recruiter_email,
        subject=f"New application from {candidate_name} — {job_title}",
        html=new_application_notification_template(candidate_name, job_title, applied_at),
    )


async def send_shortlist_notification(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    company_name: str,
) -> None:
    await _send_email(
        to=candidate_email,
        subject=f"You've been shortlisted for {job_title}!",
        html=shortlist_notification_template(candidate_name, job_title, company_name),
    )


async def send_application_status_update(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    new_status: str,
) -> None:
    status_subjects = {
        "ACCEPTED": f"Congratulations! Your application for {job_title} was accepted",
        "REJECTED": f"Update on your application for {job_title}",
        "REVIEWING": f"Your application for {job_title} is under review",
    }
    subject = status_subjects.get(new_status.upper(), f"Application status update — {job_title}")
    await _send_email(
        to=candidate_email,
        subject=subject,
        html=application_status_update_template(candidate_name, job_title, new_status),
    )
