from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.resume_model import Resume
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
)


class ResumeService:

    async def create_resume(self, db: AsyncSession, candidate_id: UUID, data: ResumeCreateSchema) -> Resume:
        resume = Resume(
            candidate_id=candidate_id,
            title=data.title,
            resume_data=data.resume_data,
        )

        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        return resume

    async def get_resumes_by_candidate_id(self, db: AsyncSession, candidate_id: UUID) -> List[Resume]:
        stmt = (
            select(Resume)
            .where(Resume.candidate_id == candidate_id)
            .order_by(Resume.created_at.desc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_resume_by_id(
            self,
            db: AsyncSession,
            resume_id: UUID,
            candidate_id: UUID,
    ) -> Resume | None:
        stmt = (
            select(Resume)
            .where(
                Resume.id == resume_id,
                Resume.candidate_id == candidate_id,
            )
        )

        result = await db.execute(stmt)
        return result.scalars().first()

    async def update_resume(
            self,
            db: AsyncSession,
            resume_id: UUID,
            candidate_id: UUID,
            data: ResumeUpdateSchema,
    ) -> Resume | None:
        resume = await self.get_resume_by_id(
            db=db,
            resume_id=resume_id,
            candidate_id=candidate_id,
        )

        if not resume:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(resume, field, value)

        await db.commit()
        await db.refresh(resume)

        return resume

    async def delete_resume(
            self,
            db: AsyncSession,
            resume_id: UUID,
            candidate_id: UUID,
    ) -> bool:
        resume = await self.get_resume_by_id(
            db=db,
            resume_id=resume_id,
            candidate_id=candidate_id,
        )

        if not resume:
            return False

        await db.delete(resume)
        await db.commit()

        return True
