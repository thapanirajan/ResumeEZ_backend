from datetime import datetime, timedelta, UTC

from jose import jwt, JWTError
from src.config.env_config import ENV
from src.utils.exceptions import AppException
from src.config.env_config import ENV


def create_jwt_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, ENV.JWT_SECRET_KEY, algorithm=ENV.ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            ENV.JWT_SECRET_KEY,
            algorithms=[ENV.ALGORITHM],
        )
        return payload
    except JWTError:
        raise AppException(
            code="INVALID_TOKEN",
            status_code=401,
            message="Invalid or expired token",
        )
