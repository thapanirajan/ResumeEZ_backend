import uuid
from datetime import datetime
from typing import Literal, Optional

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


# ─── AI Analysis Types ────────────────────────────────────────────────────────

class MatchedSkillItemSchema(BaseModel):
    name: str
    canonical_id: str
    match_type: Literal["exact", "fuzzy", "semantic"]
    confidence: float
    category: str
    years: int = 0
    weighted_score: float = 0.0


class MissingSkillItemSchema(BaseModel):
    name: str
    canonical_id: str
    category: str
    computed_weight: float
    priority_score: float
    section: Literal["required", "preferred", "general"]


class ExtraSkillItemSchema(BaseModel):
    name: str
    canonical_id: str
    category: str


class ApplicationAnalysisSchema(BaseModel):
    ats_score: int
    skills_score: int
    experience_score: int
    education_score: int
    matched_skills: list[MatchedSkillItemSchema]
    missing_skills: list[MissingSkillItemSchema]
    extra_skills: list[ExtraSkillItemSchema]
    gap_report: str
    reasoning: str


class ApplicationScoreItem(BaseModel):
    application_id: uuid.UUID
    score: int  # 0–100
    analysis: Optional[ApplicationAnalysisSchema] = None


class ExternalApplicationScoreItem(BaseModel):
    external_application_id: uuid.UUID
    score: int  # 0–100
    analysis: Optional[ApplicationAnalysisSchema] = None


class ApplicationScoresResponse(BaseModel):
    scores: list[ApplicationScoreItem]
    external_scores: list[ExternalApplicationScoreItem] = []


# ─── Skill Gap Analysis Response (for candidate endpoint) ─────────────────────

class RoadmapSkillItemSchema(BaseModel):
    name: str
    canonical_id: str
    category: str
    domain: Optional[str] = None
    is_prerequisite: bool
    priority_score: float
    subtopics: list[str] = []


class RoadmapPhasesSchema(BaseModel):
    phase_1_core: list[RoadmapSkillItemSchema] = []
    phase_2_primary: list[RoadmapSkillItemSchema] = []
    phase_3_advanced: list[RoadmapSkillItemSchema] = []


class SkillGapAnalysisResponse(BaseModel):
    analysis_id: str
    resume_id: str
    match_percentage: float
    total_jd_skills: int
    hard_skill_match: Optional[float] = None
    soft_skill_match: Optional[float] = None
    matched_skills: list[MatchedSkillItemSchema]
    missing_skills: list[MissingSkillItemSchema]
    extra_skills: list[ExtraSkillItemSchema]
    gap_report: str
    roadmap: RoadmapPhasesSchema
    ontology_version: str = "ollama-bge-v1"


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
