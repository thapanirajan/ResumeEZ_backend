import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job_model import Job, JobStatus
from src.models.user_model import User, UserRole
from src.schema.jobs_schema import JobCreateSchema, JobUpdateSchema
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


def _assert_salary_range(salary_min: int | None, salary_max: int | None) -> None:
    if salary_min is not None and salary_max is not None and salary_max < salary_min:
        raise AppException(
            ErrorCode.INVALID_INPUT,
            "salary_max must be greater than or equal to salary_min",
        )


def _get_recruiter_profile_id(current_user: User) -> uuid.UUID:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(
            ErrorCode.UNAUTHORIZED_ACCESS,
            "You are not authorized to perform this action",
        )

    recruiter_profile = getattr(current_user, "recruiter_profile", None)
    if recruiter_profile is None:
        raise AppException(
            ErrorCode.INVALID_INPUT,
            "Recruiter profile not found for this user",
        )

    return recruiter_profile.id


async def create_job_service(db: AsyncSession, payload: JobCreateSchema, current_user: User) -> Job:
    recruiter_profile_id = _get_recruiter_profile_id(current_user)

    _assert_salary_range(payload.salary_min, payload.salary_max)

    job = Job(
        recruiter_id=recruiter_profile_id,
        title=payload.title,
        description=payload.description,
        location=payload.location,
        employment_type=payload.employment_type,
        experience_required=payload.experience_required,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        application_deadline=payload.application_deadline,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def list_jobs_service(db: AsyncSession, current_user: User) -> list[Job]:
    if current_user.role == UserRole.RECRUITER:
        recruiter_profile_id = _get_recruiter_profile_id(current_user)
        stmt = (
            select(Job)
            .where(Job.recruiter_id == recruiter_profile_id)
            .order_by(Job.created_at.desc())
        )
    elif current_user.role == UserRole.ADMIN:
        stmt = select(Job).order_by(Job.created_at.desc())
    else:
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.OPEN)
            .order_by(Job.created_at.desc())
        )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_job_by_id_service(db: AsyncSession, job_id: uuid.UUID, current_user: User) -> Job:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Job not found",
        )

    if current_user.role == UserRole.RECRUITER:
        recruiter_profile_id = _get_recruiter_profile_id(current_user)
        if job.recruiter_id != recruiter_profile_id:
            raise AppException(
                ErrorCode.UNAUTHORIZED_ACCESS,
                "You are not authorized to view this job",
            )
    elif current_user.role == UserRole.ADMIN:
        pass
    else:
        if job.status != JobStatus.OPEN:
            raise AppException(
                ErrorCode.RESOURCE_NOT_FOUND,
                "Job not found",
            )

    return job


async def update_job_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    payload: JobUpdateSchema,
    current_user: User,
) -> Job:
    recruiter_profile_id = _get_recruiter_profile_id(current_user)

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Job not found",
        )

    if job.recruiter_id != recruiter_profile_id:
        raise AppException(
            ErrorCode.UNAUTHORIZED_ACCESS,
            "You are not authorized to update this job",
        )

    update_data = payload.model_dump(exclude_unset=True)

    next_salary_min = update_data.get("salary_min", job.salary_min)
    next_salary_max = update_data.get("salary_max", job.salary_max)
    _assert_salary_range(next_salary_min, next_salary_max)

    for field, value in update_data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


async def delete_job_service(db: AsyncSession, job_id: uuid.UUID, current_user: User) -> None:
    recruiter_profile_id = _get_recruiter_profile_id(current_user)

    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Job not found",
        )

    if job.recruiter_id != recruiter_profile_id:
        raise AppException(
            ErrorCode.UNAUTHORIZED_ACCESS,
            "You are not authorized to delete this job",
        )

    await db.delete(job)
    await db.commit()

