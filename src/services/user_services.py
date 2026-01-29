from typing import Optional, List, Any, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.user_model import User, UserRole


# create new user service
async def create_user_service(db: AsyncSession, username: str, email: str, password: str,
                              role: UserRole = UserRole.JOB_SEEKER, ) -> User:
    db_user = User(
        username=username,
        email=email,
        password=password,
        role=role,
    )

    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    return db_user


# get user by id
async def get_user_by_id_service(db: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.candidate_profile),
            selectinload(User.recruiter_profile),
        )
    )
    return result.scalar_one_or_none()
