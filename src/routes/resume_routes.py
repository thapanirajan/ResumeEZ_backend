from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
    ResumeResponseSchema,
    ResumeInternalCreateSchema
)
from src.services.resume_service import ResumeService
from src.utils.error_code import ErrorCode

resume_builder_router = APIRouter(prefix="/", tags=["Resume Builder"])

resume_service = ResumeService()


# POST /resumes	Create resume for authenticated candidate
@resume_builder_router.post(
    "",
    response_model=ResumeResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_resume(
        payload: ResumeCreateSchema,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(get_current_user),
):
    pass
    # resume =

# GET /resumes	List resumes owned by candidate
# GET /resumes/{id}	Get single resume (ownership enforced)
# PATCH /resumes/{id}	Partial update
# DELETE /resumes/{id}	Delete resume + cascades analyses
