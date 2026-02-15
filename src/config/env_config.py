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
    SUPABASE_PROJECT_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_CLIENT_REDIRECT_URI: str
    ACCESS_TOKEN_EXPIRE_DAYS: int


ENV_CONFIG = Env(
    DB_URL=os.getenv("DB_URL"),
    EMAIL_HOST=os.getenv("EMAIL_HOST"),
    EMAIL_PORT=int(os.getenv("EMAIL_PORT", 587)),
    EMAIL_HOST_USER=os.getenv("EMAIL_HOST_USER"),
    EMAIL_HOST_PASSWORD=os.getenv("EMAIL_HOST_PASSWORD"),
    SMTP_FROM_NAME=os.getenv("SMTP_FROM_NAME", "ResumeEZ"),
    JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
    ALGORITHM=os.getenv("ALGORITHM"),
    SUPABASE_PROJECT_URL=os.getenv("SUPABASE_PROJECT_URL"),
    SUPABASE_ANON_KEY=os.getenv("SUPABASE_ANON_KEY"),
    SUPABASE_SERVICE_KEY=os.getenv("SUPABASE_SERVICE_KEY"),
    GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID"),
    GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET"),
    GOOGLE_CLIENT_REDIRECT_URI=os.getenv("GOOGLE_CLIENT_REDIRECT_URI"),
    ACCESS_TOKEN_EXPIRE_DAYS=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 30)),
)

# Fail fast
if not ENV_CONFIG.EMAIL_HOST or not ENV_CONFIG.EMAIL_HOST_USER or not ENV_CONFIG.EMAIL_HOST_PASSWORD:
    raise RuntimeError("Email environment variables are not properly set")
