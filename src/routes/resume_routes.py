from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user, require_role
from src.models import User, Resume
from src.models.user_model import UserRole
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
    ResumeResponseSchema
)

from src.services.resume_service import ResumeService
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException
from src.utils.permissions import ownership_required

resume_builder_router = APIRouter(tags=["Resume Builder"])

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
    # Ensure profile exists
    if not candidate.candidate_profile:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="Candidate profile not found. Please set your role first."
        )

    #  calling service layer to handle resume create
    resume = await resume_service.create_resume(db, candidate.candidate_profile.id, payload)

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

    if not candidate.candidate_profile:
        return []

    resumes = await resume_service.get_resume_by_candidate(db, candidate.candidate_profile.id)

    return resumes


# -----------------------Get resume details by id --------------------------------------
# GET /resumes/{id}	Get single resume (ownership enforced)
@resume_builder_router.get("/{resource_id}", response_model=ResumeResponseSchema, status_code=status.HTTP_200_OK)
async def get_resume_by_id(
        resource_id: UUID,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    if not candidate.candidate_profile:
        raise AppException(ErrorCode.FORBIDDEN, "Candidate profile not found")

    resume = await resume_service.get_resume_by_id(db, resource_id, candidate.candidate_profile.id)
    return resume


# -----------------------------Update resume by id ---------------------------------
# PATCH /resumes/{id}	Partial update
@resume_builder_router.patch("/{resource_id}", status_code=status.HTTP_200_OK)
async def update_resume(
        payload: ResumeUpdateSchema,
        resume: Resume = Depends(
            ownership_required(
                model=Resume,
                owner_field="candidate_id",
                allowed_roles=[UserRole.JOB_SEEKER],
            )
        ),
        db: AsyncSession = Depends(get_db),
):
    await resume_service.update_resume(db, resume.id, resume.candidate_id, payload)

    return {
        "success": True,
        "message": "Resume Updated successfully"
    }


# -----------------Delete resume by id----------------------------------------
# DELETE /resumes/{id}	Delete resume + cascades analyses
@resume_builder_router.delete("/{resource_id}", status_code=status.HTTP_200_OK)
async def delete_resume(
        resume: Resume = Depends(
            ownership_required(
                model=Resume,
                owner_field="candidate_id",
                allowed_roles=[UserRole.JOB_SEEKER],
            )
        ),
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    result = await resume_service.delete_resume(db, resume.id, candidate.candidate_profile.id)

    print(result)

    return {
        "success": True,
        "message": "Resume Deleted successfully"
    }
