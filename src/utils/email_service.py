import httpx

from src.config.env_config import ENV_CONFIG
from src.utils.email_templates import (
    verification_email_template,
    new_application_notification_template,
    application_status_update_template,
    shortlist_notification_template,
)

RESEND_FROM = "ResumeEZ <onboarding@resend.dev>"


async def _send_email(to: str, subject: str, html: str) -> None:
    """Low-level helper — fire and forget, swallows errors so pipeline is never blocked."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {ENV_CONFIG.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
                timeout=10.0,
            )
            response.raise_for_status()
    except Exception as e:
        print(f"[EMAIL] Failed to send to {to}: {e}")


async def send_verification_email(email: str, token: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {ENV_CONFIG.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [email],
                "subject": "Verify your ResumeEZ account",
                "html": verification_email_template(token),
            },
            timeout=10.0,
        )
        response.raise_for_status()


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
