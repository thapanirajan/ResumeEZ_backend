import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.models.candidate_profile_model import CandidateProfile
from src.models.job_application_model import JobApplication, ApplicationStatus
from src.models.job_model import Job, JobStatus
from src.models.resume_model import Resume
from src.models.user_model import User, UserRole
from src.schema.application_schema import (
    ApplicationCreateSchema,
    ApplicationResponse,
    ApplicationDetailResponse,
)
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


def _get_candidate_profile(current_user: User):
    profile = getattr(current_user, "candidate_profile", None)
    if profile is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Candidate profile not found",
        )
    return profile


def _get_recruiter_profile(current_user: User):
    profile = getattr(current_user, "recruiter_profile", None)
    if profile is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Recruiter profile not found",
        )
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/applications/  — Candidate applies to a job
# ─────────────────────────────────────────────────────────────────────────────
async def apply_to_job_service(
    db: AsyncSession,
    payload: ApplicationCreateSchema,
    current_user: User,
) -> JobApplication:
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can apply to jobs")

    candidate_profile = _get_candidate_profile(current_user)

    # Verify job exists and is open
    job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.status != JobStatus.OPEN:
        raise AppException(ErrorCode.INVALID_INPUT, "This job is not accepting applications")

    # Verify resume belongs to this candidate
    resume_result = await db.execute(
        select(Resume).where(
            and_(
                Resume.id == payload.resume_id,
                Resume.candidate_id == candidate_profile.id,
            )
        )
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Resume not found")

    application = JobApplication(
        job_id=payload.job_id,
        candidate_id=candidate_profile.id,
        resume_id=payload.resume_id,
        cover_letter=payload.cover_letter,
    )

    db.add(application)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(ErrorCode.DUPLICATE_RESOURCE, "You have already applied to this job")

    await db.refresh(application)
    return application


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/me  — Candidate views their own applications
# ─────────────────────────────────────────────────────────────────────────────
async def get_my_applications_service(
    db: AsyncSession,
    current_user: User,
) -> list[JobApplication]:
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can view their applications")

    candidate_profile = _get_candidate_profile(current_user)

    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.candidate_id == candidate_profile.id)
        .order_by(JobApplication.applied_at.desc())
    )
    return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/check/{job_id}  — Has this candidate already applied?
# ─────────────────────────────────────────────────────────────────────────────
async def check_application_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> JobApplication | None:
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can check applications")

    candidate_profile = _get_candidate_profile(current_user)

    result = await db.execute(
        select(JobApplication).where(
            and_(
                JobApplication.job_id == job_id,
                JobApplication.candidate_id == candidate_profile.id,
            )
        )
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/job/{job_id}  — Recruiter views applications for their job
# ─────────────────────────────────────────────────────────────────────────────
async def get_applications_for_job_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> list[ApplicationDetailResponse]:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can view job applications")

    recruiter_profile = _get_recruiter_profile(current_user)

    # Verify the job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to view these applications")

    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.job_id == job_id)
        .order_by(JobApplication.applied_at.desc())
    )
    applications = list(result.scalars().all())

    # Enrich with candidate name and resume title by loading related objects
    enriched: list[ApplicationDetailResponse] = []
    for app in applications:
        candidate_result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == app.candidate_id)
        )
        candidate = candidate_result.scalar_one_or_none()

        resume_result = await db.execute(
            select(Resume).where(Resume.id == app.resume_id)
        )
        resume = resume_result.scalar_one_or_none()

        enriched.append(
            ApplicationDetailResponse(
                id=app.id,
                job_id=app.job_id,
                candidate_id=app.candidate_id,
                resume_id=app.resume_id,
                status=app.status,
                cover_letter=app.cover_letter,
                applied_at=app.applied_at,
                updated_at=app.updated_at,
                candidate_name=candidate.full_name if candidate else None,
                resume_title=resume.title if resume else None,
            )
        )

    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/applications/{application_id}/status  — Recruiter updates status
# ─────────────────────────────────────────────────────────────────────────────
async def update_application_status_service(
    db: AsyncSession,
    application_id: uuid.UUID,
    new_status: ApplicationStatus,
    current_user: User,
) -> JobApplication:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can update application status")

    recruiter_profile = _get_recruiter_profile(current_user)

    result = await db.execute(
        select(JobApplication).where(JobApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Application not found")

    # Verify the job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to update this application")

    application.status = new_status
    await db.commit()
    await db.refresh(application)
    return application
