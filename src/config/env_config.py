import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Env:
    DB_URL: str
    JWT_SECRET_KEY: str
    ALGORITHM: str
    SUPABASE_PROJECT_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_CLIENT_REDIRECT_URI: str
    ACCESS_TOKEN_EXPIRE_DAYS: int
    RESEND_API_KEY: str


ENV_CONFIG = Env(
    DB_URL=os.getenv("DB_URL"),
    JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
    ALGORITHM=os.getenv("ALGORITHM", "HS256"),
    SUPABASE_PROJECT_URL=os.getenv("SUPABASE_PROJECT_URL"),
    SUPABASE_ANON_KEY=os.getenv("SUPABASE_ANON_KEY"),
    SUPABASE_SERVICE_KEY=os.getenv("SUPABASE_SERVICE_KEY"),
    GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID"),
    GOOGLE_CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET"),
    GOOGLE_CLIENT_REDIRECT_URI=os.getenv("GOOGLE_CLIENT_REDIRECT_URI"),
    ACCESS_TOKEN_EXPIRE_DAYS=int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 30)),
    RESEND_API_KEY=os.getenv("RESEND_API_KEY")
)

# Fail fast
if not ENV_CONFIG.DB_URL:
    raise RuntimeError("DB_URL environment variable is not set")
if not ENV_CONFIG.JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is not set")
