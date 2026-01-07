from datetime import datetime, timedelta, UTC
from jose import jwt
from src.config.env_config import ENV


import bcrypt
import secrets


def hash_otp(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_otp(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())





def generate_email_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
