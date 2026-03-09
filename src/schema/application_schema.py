import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.job_application_model import ApplicationStatus
from src.models.job_model import EmploymentType, JobStatus


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
    candidate_email: Optional[str] = None
    resume_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationResumeResponse(BaseModel):
    resume_id: uuid.UUID
    resume_title: Optional[str]
    resume_data: dict

    model_config = ConfigDict(from_attributes=True)


class ApplicationScoreItem(BaseModel):
    application_id: uuid.UUID
    score: int  # 0–100


class ApplicationScoresResponse(BaseModel):
    scores: list[ApplicationScoreItem]


# ─── Schemas for get_job_with_applicants_service ──────────────────────────────

class ResumeInApplicationSchema(BaseModel):
    id: uuid.UUID
    title: str
    resume_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CandidateInApplicationSchema(BaseModel):
    id: uuid.UUID
    full_name: Optional[str]
    username: Optional[str]
    current_role: Optional[str]
    experience_years: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class ApplicationWithDetailsSchema(BaseModel):
    id: uuid.UUID
    status: ApplicationStatus
    cover_letter: Optional[str]
    applied_at: datetime
    updated_at: datetime
    candidate: CandidateInApplicationSchema
    resume: ResumeInApplicationSchema

    model_config = ConfigDict(from_attributes=True)


class JobWithApplicantsSchema(BaseModel):
    id: uuid.UUID
    recruiter_id: uuid.UUID
    title: str
    description: str
    location: Optional[str]
    employment_type: EmploymentType
    experience_required: Optional[int]
    salary_min: Optional[int]
    salary_max: Optional[int]
    application_deadline: Optional[datetime]
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    applications: list[ApplicationWithDetailsSchema]

    model_config = ConfigDict(from_attributes=True)
