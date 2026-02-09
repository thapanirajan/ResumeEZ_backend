from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user, require_role
from src.models import User
from src.models.user_model import UserRole
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
    ResumeResponseSchema,
    ResumeInternalCreateSchema
)
from src.services.auth_services import get_user_by_id
from src.services.resume_service import ResumeService
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException

resume_builder_router = APIRouter(prefix="/", tags=["Resume Builder"])

resume_service = ResumeService()


# POST /resumes	Create resume for authenticated candidate
# -----------------Create Resume -----------------------------------------------
@resume_builder_router.post(
    "",
    response_model=ResumeResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_resume(
        payload: ResumeCreateSchema,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER)),
):
    #  calling service layer to handle resume create
    resume = await  resume_service.create_resume(db, candidate.id, payload)

    return resume


# ----------------------Get a list of resumes created by logged-in user ------------------------------------------
# GET /resumes	List resumes owned by candidate
@resume_builder_router.get("", response_model=List[ResumeResponseSchema], status_code=status.HTTP_200_OK)
async def get_candidate_resumes(
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(get_current_user)
):
    # Route level authorization
    if candidate.role != UserRole.JOB_SEEKER:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="Only Candidates can create resumes."
        )

    resumes = await  resume_service.get_resume_by_candidate(db, candidate.id)

    return resumes


#-----------------------Get resume details by id --------------------------------------
# GET /resumes/{id}	Get single resume (ownership enforced)
@resume_builder_router.get("/{resume_id}", response_model=ResumeResponseSchema, status_code=status.HTTP_200_OK)
async def get_resume_by_id(
        db: AsyncSession,
        resume_id: UUID,
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    resume = await resume_service.get_resume_by_id(db, resume_id, candidate.id)
    return resume


# -----------------------------Update resume by id ---------------------------------
# PATCH /resumes/{id}	Partial update
@resume_builder_router.patch("/{resume_id}", status_code=status.HTTP_200_OK)
async def update_resume(
        resume_id: UUID,
        payload: ResumeUpdateSchema,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    await resume_service.update_resume(db, resume_id, candidate.id, payload)

    return {
        "success": True,
        "message": "Resume Updated successfully"
    }


# -----------------Delete resume by id----------------------------------------
# DELETE /resumes/{id}	Delete resume + cascades analyses
@resume_builder_router.delete("/{resume_id}", status_code=status.HTTP_200_OK)
async def delete_resume(
        resume_id: UUID,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    await resume_service.delete_resume(db, resume_id, candidate.id)

    return {
        "success": True,
        "message": "Resume Deleted successfully"
    }
