import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.models.external_application_model import (
    ExternalApplicationSource,
    ExternalApplicationStatus,
)


class ExternalApplicationCreateSchema(BaseModel):
    candidate_name: str
    candidate_email: Optional[str] = None
    source: ExternalApplicationSource = ExternalApplicationSource.OTHER
    notes: Optional[str] = None

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class ExternalApplicationStatusUpdateSchema(BaseModel):
    status: ExternalApplicationStatus

    model_config = ConfigDict(extra="forbid")


class ExternalApplicationNotesUpdateSchema(BaseModel):
    recruiter_notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class ExternalBulkStatusUpdateSchema(BaseModel):
    external_application_ids: list[uuid.UUID]
    status: ExternalApplicationStatus

    model_config = ConfigDict(extra="forbid")


class ExternalApplicationResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    candidate_name: str
    candidate_email: Optional[str]
    source: ExternalApplicationSource
    resume_file_url: str
    resume_filename: str
    status: ExternalApplicationStatus
    notes: Optional[str]
    recruiter_notes: Optional[str] = None
    ai_score: Optional[int] = None
    ai_analysis: Optional[dict] = None
    ai_scored_at: Optional[datetime] = None
    uploaded_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkUploadResultItem(BaseModel):
    filename: str
    success: bool
    data: Optional[ExternalApplicationResponse] = None
    error: Optional[str] = None


class BulkUploadResponse(BaseModel):
    results: list[BulkUploadResultItem]
    uploaded_count: int
    failed_count: int
