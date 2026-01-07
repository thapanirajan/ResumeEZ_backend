from typing import Optional, List, Any, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
async def get_user_by_id_service(db: AsyncSession, user_id: str, ) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# get all users
async def get_all_users_service(db: AsyncSession, skip: int = 0, limit: int = 10, ) -> Sequence[User]:
    result = await db.execute(
        select(User)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()
