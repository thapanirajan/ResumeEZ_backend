import httpx

from src.config.env_config import ENV_CONFIG
from src.utils.email_templates import verification_email_template

RESEND_FROM = "ResumeEZ <onboarding@resend.dev>"


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
