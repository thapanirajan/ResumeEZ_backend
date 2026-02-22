import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from src.models.job_model import EmploymentType, JobStatus


# ------------------- Create JOb Schema -----------------------
class JobCreateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    location: Optional[str] = Field(None, max_length=255)
    employment_type: EmploymentType
    experience_required: Optional[int] = Field(None, ge=0)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    application_deadline: Optional[datetime] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    @field_validator("salary_max")
    @classmethod
    def validate_salary(cls, v, info):
        salary_min = info.data.get("salary_min")
        if v is not None and salary_min is not None:
            if v < salary_min:
                raise ValueError("salary_max must be greater than or equal to salary_min")
        return v


# ----------------------Update job schema ----------------------------
class JobUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    location: Optional[str] = Field(None, max_length=255)
    employment_type: Optional[EmploymentType] = None
    experience_required: Optional[int] = Field(None, ge=0)
    salary_min: Optional[int] = Field(None, ge=0)
    salary_max: Optional[int] = Field(None, ge=0)
    application_deadline: Optional[datetime] = None
    status: Optional[JobStatus] = None

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

    @field_validator("salary_max")
    @classmethod
    def validate_salary(cls, v, info):
        salary_min = info.data.get("salary_min")
        if v is not None and salary_min is not None:
            if v < salary_min:
                raise ValueError("salary_max must be >= salary_min")
        return v


class JobResponse(BaseModel):
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

    model_config = ConfigDict(
        from_attributes=True
    )
