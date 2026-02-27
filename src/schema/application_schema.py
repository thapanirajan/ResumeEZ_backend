import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.job_application_model import ApplicationStatus


class ApplicationCreateSchema(BaseModel):
    job_id: uuid.UUID
    resume_id: uuid.UUID
    cover_letter: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ApplicationStatusUpdateSchema(BaseModel):
    status: ApplicationStatus

    model_config = ConfigDict(extra="forbid")


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID
    status: ApplicationStatus
    cover_letter: Optional[str]
    applied_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Richer response for recruiter view – includes candidate name & resume title
class ApplicationDetailResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    resume_id: uuid.UUID
    status: ApplicationStatus
    cover_letter: Optional[str]
    applied_at: datetime
    updated_at: datetime

    # Joined fields (populated manually in service)
    candidate_name: Optional[str] = None
    resume_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
