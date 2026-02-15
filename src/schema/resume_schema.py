from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List


class ResumeCreateSchema(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    resume_data: Dict[str, Any]


class ResumeUpdateSchema(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    resume_data: Optional[Dict[str, Any]] = None


class ResumeResponseSchema(BaseModel):
    id: UUID
    candidate_id: UUID

    title: str
    resume_data: Dict[str, Any]

    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CandidateResumeListResponseSchema(BaseModel):
    success: bool = True
    message: str
    data: List[ResumeResponseSchema]

class ResumeInternalCreateSchema(ResumeCreateSchema):
    candidate_id: UUID

