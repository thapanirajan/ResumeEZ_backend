from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List
from uuid import UUID
from datetime import datetime


class JobCreateSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(
        None,
        description="Raw job description text (copy-paste)"
    )
    jd_file_url: Optional[str] = Field(
        None,
        description="Uploaded JD file URL (PDF/DOC)"
    )
    confirm_check: Optional[bool] = Field(
        False, 
        description="Flag to confirm creation despite duplicate warning"
    )

    model_config = ConfigDict(from_attributes=True)


class SkillItemSchema(BaseModel):
    name: str = Field(..., min_length=1)
    weight: float = Field(..., ge=0.0, le=1.0)


class RequiredSkillsSchema(BaseModel):
    must_have: List[SkillItemSchema] = Field(default_factory=list)
    good_to_have: List[SkillItemSchema] = Field(default_factory=list)
    experience: Optional[dict] = None


class JobSkillUpdateSchema(BaseModel):
    required_skills: RequiredSkillsSchema

    model_config = ConfigDict(from_attributes=True)


class JobResponseSchema(BaseModel):
    id: UUID
    title: str
    description: str
    status: str
    processing_status: str
    experience_level: Optional[str] = None
    education: Optional[dict] = None
    required_skills: Optional[RequiredSkillsSchema]

    model_config = ConfigDict(from_attributes=True)
