import uuid

from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user, require_role
from src.models import User
from src.models.user_model import UserRole
from src.schema.jobs_schema import JobCreateSchema, JobUpdateSchema, JobResponse
from src.services.job_services import (
    create_job_service,
    delete_job_service,
    get_job_by_id_service,
    list_jobs_service,
    update_job_service,
)

job_router = APIRouter(tags=["Jobs"])


@job_router.post("/", status_code=status.HTTP_201_CREATED, response_model=JobResponse)
async def create_job(
    payload: JobCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
):
    return await create_job_service(db, payload, current_user)


@job_router.get("/", response_model=list[JobResponse])
async def get_all_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_jobs_service(db, current_user)


@job_router.get("/{job_id}", response_model=JobResponse)
async def get_job_by_id(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_job_by_id_service(db, job_id, current_user)


@job_router.patch("/{job_id}", response_model=JobResponse)
async def edit_job(
    job_id: uuid.UUID,
    payload: JobUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
):
    return await update_job_service(db, job_id, payload, current_user)


@job_router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.RECRUITER)),
):
    await delete_job_service(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
