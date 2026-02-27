import uuid
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job_model import Job, JobStatus
from src.models.user_model import User, UserRole
from src.schema.jobs_schema import JobCreateSchema, JobUpdateSchema, JobFilterSchema
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

    print(recruiter_profile_id)

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


async def list_jobs_service(db: AsyncSession, current_user: User, filters: JobFilterSchema) -> list[Job]:
    conditions = []

    if filters.status is not None:
        conditions.append(Job.status == filters.status)
    else:
        conditions.append(Job.status == JobStatus.OPEN)

    if filters.title:
        conditions.append(Job.title.ilike(f"%{filters.title}%"))

    if filters.description:
        conditions.append(Job.description.ilike(f"%{filters.description}%"))

    if filters.location:
        conditions.append(Job.location.ilike(f"%{filters.location}%"))

    if filters.employment_types:
        conditions.append(Job.employment_type.in_(filters.employment_types))

    if filters.min_experience is not None:
        conditions.append(Job.experience_required >= filters.min_experience)

    if filters.max_experience is not None:
        conditions.append(Job.experience_required <= filters.max_experience)

    if filters.min_salary is not None:
        conditions.append(Job.salary_min >= filters.min_salary)

    if filters.max_salary is not None:
        conditions.append(Job.salary_max <= filters.max_salary)

    if filters.deadline_from:
        conditions.append(Job.application_deadline >= filters.deadline_from)

    if filters.deadline_to:
        conditions.append(Job.application_deadline <= filters.deadline_to)

    if filters.only_active:
        now = datetime.now(timezone.utc)
        conditions.append(
            or_(Job.application_deadline.is_(None), Job.application_deadline >= now)
        )

    if filters.created_after:
        conditions.append(Job.created_at >= filters.created_after)

    if filters.created_before:
        conditions.append(Job.created_at <= filters.created_before)

    sort_col_name = filters.sort_by or "created_at"
    sort_column = getattr(Job, sort_col_name)
    order_expr = sort_column.asc() if filters.order == "asc" else sort_column.desc()

    stmt = select(Job).where(and_(*conditions)).order_by(order_expr)
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



# ---------------- Returns all the jobs posted by logged-in user (recruiter)
# ---------------- db , current_user : User object
async def get_jobs_by_recruiter_service(db: AsyncSession, current_user: User):

    recruiter_profile_id = _get_recruiter_profile_id(current_user)
    result = await db.execute(
        select(Job)
        .where(Job.recruiter_id == recruiter_profile_id)
        .order_by(Job.created_at.desc())
    )

    return result.scalars().all()

