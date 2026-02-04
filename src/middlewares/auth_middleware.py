from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.models.user_model import UserRole, User
from src.services.user_services import get_user_by_id_service
from src.utils.error_code import ErrorCode
from src.utils.jwt_utils import decode_jwt_token
from src.utils.exceptions import AppException
from fastapi import Request


# role checker
def require_role(required_role: UserRole):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role != required_role:
            raise AppException(
                ErrorCode.UNAUTHORIZED_ACCESS,
                "You are not authorized to perform this action",
            )
        return current_user

    return role_checker


# authenticate
async def get_current_user(
        req: Request,
        db: AsyncSession = Depends(get_db)
) -> User:
    token = req.cookies.get("token")
    if not token:
        raise AppException(
            ErrorCode.AUTHENTICATION_FAILED,
            "Not authenticated"
        )

    print("---------jwt token-------------")
    print(token)

    payload = decode_jwt_token(token)

    print(payload)

    user_id: str | None = payload.get("sub")

    if not user_id:
        raise AppException(
            code="INVALID_TOKEN",
            status_code=401,
            message="Invalid token payload",
        )

    user = await get_user_by_id_service(db, UUID(user_id))

    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            status_code=401,
            message="User not found",
        )

    return user
