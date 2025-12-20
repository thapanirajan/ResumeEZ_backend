import aiosmtplib
from email.message import EmailMessage

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "nirajanth2023@gmail.com"
EMAIL_HOST_PASSWORD = "pgejkbgalvnjdcnq"


async def send_verification_email(email: str, token: str):
    msg = EmailMessage()
    msg["Subject"] = "Verification Email"
    msg["From"] = EMAIL_HOST_USER
    msg["To"] = email
    msg.set_content("Verification Email Code: " + token)

    await aiosmtplib.send(
        msg,
        hostname=EMAIL_HOST,
        port=EMAIL_PORT,
        username=EMAIL_HOST_USER,
        password=EMAIL_HOST_PASSWORD,
        start_tls=True,
    )
