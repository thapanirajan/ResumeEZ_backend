from datetime import datetime, timedelta, UTC

from jose import jwt, JWTError
from src.config.env_config import ENV_CONFIG
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException
from src.config.env_config import ENV_CONFIG


def create_jwt_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, ENV_CONFIG.JWT_SECRET_KEY, algorithm=ENV_CONFIG.ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            ENV_CONFIG.JWT_SECRET_KEY,
            algorithms=[ENV_CONFIG.ALGORITHM],
        )
        return payload
    except JWTError:
        raise AppException(
            ErrorCode.INVALID_TOKEN,
            "Invalid or expired token"
        )
