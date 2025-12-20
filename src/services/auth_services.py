from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import User
from src.schema.user_schema import UpdateUserSchema
from sqlalchemy import select, update


async def register_user_service(db: AsyncSession, user_data: dict):
    user = User(**user_data)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_email(db: AsyncSession, email: str):
    user = await db.execute(select(User).where(User.email == email))
    return user.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str):
    user = await db.execute(select(User).where(User.id == user_id))
    return user.scalar_one_or_none()


async def update_user(db: AsyncSession, user_data: UpdateUserSchema, user_id: str):
    result = await  db.execute(
        update(User)
        .where(User.id == user_id)
        .values(**user_data)
        .execution_options(synchronize_session='fetch')
    )

    await db.commit()

    return await get_user_by_id(db, user_id)
