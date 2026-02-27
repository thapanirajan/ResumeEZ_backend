import uuid
from datetime import datetime
from typing import Optional, List

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


class JobFilterSchema(BaseModel):
    # ---------------- TEXT SEARCH ----------------
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    location: Optional[str] = Field(None, min_length=2, max_length=255)

    # ---------------- ENUM FILTERS ----------------
    employment_types: Optional[List[EmploymentType]] = None
    status: Optional[JobStatus] = None

    # ---------------- EXPERIENCE FILTER ----------------
    min_experience: Optional[int] = Field(None, ge=0)
    max_experience: Optional[int] = Field(None, ge=0)

    # ---------------- SALARY FILTER ----------------
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)

    # ---------------- DEADLINE FILTER ----------------
    deadline_from: Optional[datetime] = None
    deadline_to: Optional[datetime] = None
    only_active: Optional[bool] = None  # not expired

    # ---------------- DATE FILTER ----------------
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


    # ---------------- SORTING ----------------
    sort_by: Optional[str] = Field(
        default="created_at",
        pattern="^(created_at|salary_min|salary_max|experience_required|application_deadline)$"
    )
    order: Optional[str] = Field(
        default="desc",
        pattern="^(asc|desc)$"
    )

    # ---------------- PAGINATION ----------------
    page: Optional[int] = Field(default=1, ge=1)
    limit: Optional[int] = Field(default=10, ge=1, le=100)
