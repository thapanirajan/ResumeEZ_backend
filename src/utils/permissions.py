from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Type

from src.config.db import get_db
from src.middlewares.auth_middleware import require_role
from src.models.user_model import User, UserRole
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


def ownership_required(
    model: Type, # example Resume model, User model
    owner_field: str,
    allowed_roles: list[UserRole],
):
    async def dependency(
        resource_id: UUID,
        db: AsyncSession = Depends(get_db),
        user: User = Depends(require_role(*allowed_roles)),
    ):
        # Fetch resource
        stmt = select(model).where(model.id == resource_id)
        result = await db.execute(stmt)
        instance = result.scalar_one_or_none()

        if not instance:
            raise AppException(
                code=ErrorCode.RESOURCE_NOT_FOUND,
                message=f"{model.__name__} not found",
            )

        # Ownership check using logged-in user's ID or profile IDs
        owner_id = getattr(instance, owner_field)

        authorized = False
        if owner_id == user.id:
            authorized = True
        elif hasattr(user, "candidate_profile") and user.candidate_profile and owner_id == user.candidate_profile.id:
            authorized = True
        elif hasattr(user, "recruiter_profile") and user.recruiter_profile and owner_id == user.recruiter_profile.id:
            authorized = True

        if not authorized:
            raise AppException(
                code=ErrorCode.FORBIDDEN,
                message="You do not own this resource",
            )

        return instance

    return dependency
