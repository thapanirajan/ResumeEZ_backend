from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import RecruiterProfile


async def get_recruiter_by_id(db: AsyncSession, recruiter_id: int):
    recruiter = await db.execute(
        Select(RecruiterProfile)
        .where(RecruiterProfile.id == recruiter_id)
    )
    return recruiter.scalar_one_or_none()
