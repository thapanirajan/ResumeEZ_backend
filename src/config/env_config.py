import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Env:
    DB_URL: str
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_HOST_USER: str
    EMAIL_HOST_PASSWORD: str
    SMTP_FROM_NAME: str
    JWT_SECRET_KEY: str
    ALGORITHM: str


ENV = Env(
    DB_URL=os.getenv("DB_URL"),
    EMAIL_HOST=os.getenv("EMAIL_HOST"),
    EMAIL_PORT=int(os.getenv("EMAIL_PORT", 587)),
    EMAIL_HOST_USER=os.getenv("EMAIL_HOST_USER"),
    EMAIL_HOST_PASSWORD=os.getenv("EMAIL_HOST_PASSWORD"),
    SMTP_FROM_NAME=os.getenv("SMTP_FROM_NAME", "ResumeEZ"),
    JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
    ALGORITHM=os.getenv("ALGORITHM"),
)

# Fail fast
if not ENV.EMAIL_HOST or not ENV.EMAIL_HOST_USER or not ENV.EMAIL_HOST_PASSWORD:
    raise RuntimeError("Email environment variables are not properly set")
