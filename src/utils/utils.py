from datetime import datetime, timedelta, UTC
from jose import jwt

SECRET_KEY = "askjdfhqweh2wh3w2werbn234bbjwer"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

import bcrypt
import secrets


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_jwt_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_email_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
