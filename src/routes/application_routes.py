import uuid
from typing import List

from fastapi import APIRouter, Depends, status, Response, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.models.job_application_model import ApplicationStatus
from src.models.external_application_model import ExternalApplicationSource, ExternalApplicationStatus
from src.schema.application_schema import (
    ApplicationCreateSchema,
    ApplicationResponse,
    ApplicationDetailResponse,
    ApplicationResumeResponse,
    ApplicationScoresResponse,
    ApplicationStatusUpdateSchema,
    JobWithApplicantsSchema,
)
from src.schema.external_application_schema import (
    ExternalApplicationCreateSchema,
    ExternalApplicationResponse,
    ExternalApplicationStatusUpdateSchema,
)
from src.services.application_service import (
    apply_to_job_service,
    check_application_service,
    get_applications_for_job_service,
    get_my_applications_service,
    update_application_status_service,
    get_job_with_applicants_service,
    get_application_resume_service,
    score_applications_for_job_service,
)
from src.services.external_application_service import (
    upload_external_application_service,
    get_external_applications_service,
    update_external_application_status_service,
)

application_router = APIRouter(tags=["Applications"])


# ─── POST /api/applications/ ─────────────────────────────────────────────────
@application_router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationResponse,
)
async def apply_to_job(
    payload: ApplicationCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await apply_to_job_service(db, payload, current_user)


# ─── GET /api/applications/me ────────────────────────────────────────────────
@application_router.get(
    "/me",
    response_model=List[ApplicationResponse],
)
async def get_my_applications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_my_applications_service(db, current_user)


# ─── GET /api/applications/check/{job_id} ────────────────────────────────────
# Returns the application if the candidate has already applied, 404 otherwise
@application_router.get(
    "/check/{job_id}",
    response_model=ApplicationResponse,
)
async def check_application(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from src.utils.error_code import ErrorCode
    from src.utils.exceptions import AppException

    application = await check_application_service(db, job_id, current_user)
    if application is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Not applied")
    return application


# ─── GET /api/applications/job/{job_id} ──────────────────────────────────────
@application_router.get(
    "/job/{job_id}",
    response_model=List[ApplicationDetailResponse],
)
async def get_applications_for_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    applicants = await get_applications_for_job_service(db, job_id, current_user)
    print(applicants)
    return  applicants

# ─── GET /api/applications/job/{job_id}/with-applicants ──────────────────────
@application_router.get(
    "/job/{job_id}/with-applicants",
    response_model=JobWithApplicantsSchema,
)
async def get_job_with_applicants(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_job_with_applicants_service(db, job_id, current_user)


# ─── GET /api/applications/job/{job_id}/ai-scores ────────────────────────────
@application_router.get(
    "/job/{job_id}/ai-scores",
    response_model=ApplicationScoresResponse,
)
async def score_applications_for_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await score_applications_for_job_service(db, job_id, current_user)


# ─── GET /api/applications/{application_id}/resume ───────────────────────────
@application_router.get(
    "/{application_id}/resume",
    response_model=ApplicationResumeResponse,
)
async def get_application_resume(
    application_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_application_resume_service(db, application_id, current_user)


# ─── PATCH /api/applications/{application_id}/status ─────────────────────────
@application_router.patch(
    "/{application_id}/status",
    response_model=ApplicationResponse,
)
async def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_application_status_service(
        db, application_id, payload.status, current_user
    )


# ─── POST /api/applications/job/{job_id}/external ────────────────────────────
@application_router.post(
    "/job/{job_id}/external",
    status_code=status.HTTP_201_CREATED,
    response_model=ExternalApplicationResponse,
)
async def upload_external_resume(
    job_id: uuid.UUID,
    file: UploadFile = File(...),
    candidate_name: str = Form(...),
    candidate_email: str | None = Form(default=None),
    source: ExternalApplicationSource = Form(default=ExternalApplicationSource.OTHER),
    notes: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = ExternalApplicationCreateSchema(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        source=source,
        notes=notes,
    )
    return await upload_external_application_service(db, job_id, payload, file, current_user)


# ─── GET /api/applications/job/{job_id}/external ─────────────────────────────
@application_router.get(
    "/job/{job_id}/external",
    response_model=List[ExternalApplicationResponse],
)
async def get_external_applications(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_external_applications_service(db, job_id, current_user)


# ─── PATCH /api/applications/external/{external_id}/status ───────────────────
@application_router.patch(
    "/external/{external_id}/status",
    response_model=ExternalApplicationResponse,
)
async def update_external_application_status(
    external_id: uuid.UUID,
    payload: ExternalApplicationStatusUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await update_external_application_status_service(
        db, external_id, payload.status, current_user
    )
