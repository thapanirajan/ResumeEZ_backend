from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.models.user_model import UserRole
from src.schema.jobs_schema import JobResponseSchema, JobCreateSchema
from src.services.job_services import handle_create_job
from src.utils.exceptions import AppException
from src.utils.error_code import ErrorCode

job_router = APIRouter(prefix="/", tags=["Jobs"])


@job_router.post("/", status_code=status.HTTP_201_CREATED, response_model=JobResponseSchema)
async def create_job(
        payload: JobCreateSchema,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.RECRUITER:
        raise AppException(
            code=ErrorCode.UNAUTHORIZED_ACCESS,
            message="You are not authorized to perform this action",
        )
    if not payload.description and not payload.jd_file_url:
        raise AppException(
            code=ErrorCode.INVALID_INPUT,
            message="Please provide description or JD file url",
        )

    job = await handle_create_job(db, payload, current_user.id)

    return job

# Delete job
# Update job
# View all jobs
# View single job
