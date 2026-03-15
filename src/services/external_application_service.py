import uuid
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.supabase_config import supabase
from src.models.external_application_model import ExternalApplication, ExternalApplicationStatus
from src.models.job_model import Job
from src.models.user_model import User, UserRole
from src.schema.external_application_schema import (
    ExternalApplicationCreateSchema,
    ExternalApplicationResponse,
    BulkUploadResultItem,
    BulkUploadResponse,
)
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException

BUCKET_NAME = "document"


def _get_recruiter_profile(current_user: User):
    profile = getattr(current_user, "recruiter_profile", None)
    if profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Recruiter profile not found")
    return profile


async def _upload_file_to_supabase(file: UploadFile) -> tuple[str, str]:
    """Upload file to Supabase and return (url, original_filename)."""
    file_ext = (file.filename or "resume").rsplit(".", 1)[-1]
    unique_filename = f"external/{uuid4().hex}.{file_ext}"

    file_content = await file.read()
    await file.seek(0)

    try:
        supabase.storage.from_(BUCKET_NAME).upload(unique_filename, file_content)
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
    except Exception as e:
        raise AppException(ErrorCode.INTERNAL_ERROR, f"File upload failed: {e}")

    if not public_url:
        raise AppException(ErrorCode.INTERNAL_ERROR, "Failed to get public URL from storage")

    return public_url, file.filename or unique_filename


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/applications/job/{job_id}/external
# ─────────────────────────────────────────────────────────────────────────────
async def upload_external_application_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    payload: ExternalApplicationCreateSchema,
    file: UploadFile,
    current_user: User,
) -> ExternalApplication:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can upload external resumes")

    recruiter_profile = _get_recruiter_profile(current_user)

    # Verify job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to upload resumes for this job")

    # Upload file
    resume_url, original_filename = await _upload_file_to_supabase(file)

    external_app = ExternalApplication(
        job_id=job_id,
        candidate_name=payload.candidate_name,
        candidate_email=payload.candidate_email,
        source=payload.source,
        resume_file_url=resume_url,
        resume_filename=original_filename,
        notes=payload.notes,
    )

    db.add(external_app)
    await db.commit()
    await db.refresh(external_app)
    return external_app


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/applications/job/{job_id}/external/bulk
# ─────────────────────────────────────────────────────────────────────────────
async def bulk_upload_external_applications_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    files: list[UploadFile],
    candidate_names: list[str],
    source: "ExternalApplicationSource",
    notes: str | None,
    current_user: User,
) -> BulkUploadResponse:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can upload external resumes")

    recruiter_profile = _get_recruiter_profile(current_user)

    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to upload resumes for this job")

    results: list[BulkUploadResultItem] = []

    # ── Phase 1: upload files to Supabase (independent, no DB involved) ───────
    # Collect (candidate_name, resume_url, original_filename) for successes
    upload_successes: list[tuple[str, str, str]] = []  # (name, url, filename)

    for idx, file in enumerate(files):
        raw_filename = file.filename or f"resume_{idx + 1}"
        candidate_name = (
            candidate_names[idx].strip()
            if idx < len(candidate_names) and candidate_names[idx].strip()
            else raw_filename.rsplit(".", 1)[0]
        )
        try:
            resume_url, original_filename = await _upload_file_to_supabase(file)
            upload_successes.append((candidate_name, resume_url, original_filename))
            results.append(BulkUploadResultItem(filename=raw_filename, success=True))
        except Exception as e:
            results.append(BulkUploadResultItem(filename=raw_filename, success=False, error=str(e)))

    if not upload_successes:
        return BulkUploadResponse(results=results, uploaded_count=0, failed_count=len(results))

    # ── Phase 2: insert all successful uploads in a single DB transaction ─────
    new_apps: list[ExternalApplication] = []
    for candidate_name, resume_url, original_filename in upload_successes:
        ext_app = ExternalApplication(
            job_id=job_id,
            candidate_name=candidate_name,
            source=source,
            resume_file_url=resume_url,
            resume_filename=original_filename,
            notes=notes,
        )
        db.add(ext_app)
        new_apps.append(ext_app)

    try:
        await db.commit()
        for ext_app in new_apps:
            await db.refresh(ext_app)
    except Exception as e:
        await db.rollback()
        # Mark all previously-successful results as failed
        commit_error = f"Database commit failed: {e}"
        success_idx = 0
        for r in results:
            if r.success:
                r.success = False
                r.error = commit_error
                success_idx += 1
        return BulkUploadResponse(results=results, uploaded_count=0, failed_count=len(results))

    # Attach DB records to their corresponding result items
    app_iter = iter(new_apps)
    for r in results:
        if r.success:
            r.data = ExternalApplicationResponse.model_validate(next(app_iter))

    uploaded = sum(1 for r in results if r.success)
    failed = len(results) - uploaded
    return BulkUploadResponse(results=results, uploaded_count=uploaded, failed_count=failed)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/job/{job_id}/external
# ─────────────────────────────────────────────────────────────────────────────
async def get_external_applications_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> list[ExternalApplicationResponse]:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can view external applications")

    recruiter_profile = _get_recruiter_profile(current_user)

    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to view external applications for this job")

    result = await db.execute(
        select(ExternalApplication)
        .where(ExternalApplication.job_id == job_id)
        .order_by(ExternalApplication.uploaded_at.desc())
    )
    applications = list(result.scalars().all())
    return [ExternalApplicationResponse.model_validate(a) for a in applications]


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/applications/external/{external_id}/status
# ─────────────────────────────────────────────────────────────────────────────
async def update_external_application_status_service(
    db: AsyncSession,
    external_id: uuid.UUID,
    new_status: ExternalApplicationStatus,
    current_user: User,
) -> ExternalApplication:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can update application status")

    recruiter_profile = _get_recruiter_profile(current_user)

    result = await db.execute(
        select(ExternalApplication).where(ExternalApplication.id == external_id)
    )
    ext_app = result.scalar_one_or_none()
    if ext_app is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "External application not found")

    job_result = await db.execute(select(Job).where(Job.id == ext_app.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "Not authorized to update this application")

    ext_app.status = new_status
    await db.commit()
    await db.refresh(ext_app)
    return ext_app
