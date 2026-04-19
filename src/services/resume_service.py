from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from src.models.resume_model import Resume
from src.models.skill_gap_report_model import SkillGapReport
from src.models.learning_roadmap_model import LearningRoadmap
from src.models.job_application_model import JobApplication
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
)
from src.utils.exceptions import AppException


class ResumeService:

    # ------------------------- Create Resume ---------------------------------------------
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



    # ------------------------- Get Resume By Candidate ID  ---------------------------------------------
    async def get_resumes_by_candidate_id(self, db: AsyncSession, candidate_id: UUID) -> List[Resume]:
        stmt = (
            select(Resume)
            .where(Resume.candidate_id == candidate_id)
            .order_by(Resume.created_at.desc())
        )

        result = await db.execute(stmt)
        return result.scalars().all()




    # ------------------------- Get Resume By Id ---------------------------------------------
    async def get_resume_by_id(
            self,
            db: AsyncSession,
            resume_id: UUID,
            candidate_id: UUID,
    ) -> Resume | None:
        resume = await self.get_resume_by_id_unscoped(db=db, resume_id=resume_id)
        if resume is None:
            return None
        if resume.candidate_id != candidate_id:
            return None
        return resume

    async def get_resume_by_id_unscoped(
            self,
            db: AsyncSession,
            resume_id: UUID,
    ) -> Resume | None:
        stmt = (
            select(Resume)
            .where(
                Resume.id == resume_id,
            )
        )

        result = await db.execute(stmt)
        return result.scalars().first()

    # ------------------------- Update Resume ---------------------------------------------
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

    # ------------------------- Delete Resume ---------------------------------------------
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

        # If a resume is used for job applications, we shouldn't delete it because it would
        # break application history and violate FK constraints.
        app_stmt = select(JobApplication.id).where(JobApplication.resume_id == resume_id).limit(1)
        app_result = await db.execute(app_stmt)
        if app_result.scalar_one_or_none() is not None:
            raise AppException(
                code="RESUME_IN_USE",
                message="This resume is used in a job application and can't be deleted.",
                status_code=409,
            )

        # Clean up derived/secondary records referencing this resume.
        # Delete roadmaps first (FK -> skill_gap_reports), then delete reports.
        report_ids_stmt = select(SkillGapReport.id).where(
            SkillGapReport.resume_id == resume_id,
            SkillGapReport.candidate_id == candidate_id,
        )
        await db.execute(delete(LearningRoadmap).where(LearningRoadmap.report_id.in_(report_ids_stmt)))
        await db.execute(
            delete(SkillGapReport).where(
                SkillGapReport.resume_id == resume_id,
                SkillGapReport.candidate_id == candidate_id,
            )
        )

        try:
            await db.delete(resume)
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise AppException(
                code="RESUME_DELETE_CONFLICT",
                message="Cannot delete this resume because it is referenced by other records.",
                status_code=409,
                details={"error": str(e)},
            )

        return True
