

import aiosmtplib
from email.message import EmailMessage

from src.config.env_config import ENV_CONFIG
from src.utils.email_templates import verification_email_template


async def send_verification_email(email: str, token: str):
    msg = EmailMessage()
    msg["Subject"] = "Verify your ResumeEZ account"
    msg["From"] = f"{ENV_CONFIG.SMTP_FROM_NAME} <{ENV_CONFIG.EMAIL_HOST_USER}>"
    msg["To"] = email
    msg.set_content(verification_email_template(token), subtype="html")

    await aiosmtplib.send(
        msg,
        hostname=ENV_CONFIG.EMAIL_HOST,
        port=ENV_CONFIG.EMAIL_PORT,
        username=ENV_CONFIG.EMAIL_HOST_USER,
        password=ENV_CONFIG.EMAIL_HOST_PASSWORD,
        start_tls=True,
    )
