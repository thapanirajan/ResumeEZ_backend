from sqlalchemy import Select, Uuid
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CandidateProfile
from src.schema.candidate_schema import UpdateCandidateSchema


async def get_candidate_by_id(db: AsyncSession, candidate_id: str):
    result = await db.execute(
        Select(CandidateProfile)
        .where(CandidateProfile.user_id == candidate_id)
    )

    return result.scalar_one_or_none()


async def update_candidate_profile(db: AsyncSession, candidate_profile_id: str, data: UpdateCandidateSchema):
    result = await db.execute(
        Select(CandidateProfile)
        .where(CandidateProfile.user_id == candidate_profile_id)
    )

    candidate = result.scalar_one_or_none()

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(candidate, field, value)

    await db.commit()
    await db.refresh(candidate)

    return candidate
