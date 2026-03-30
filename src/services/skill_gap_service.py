"""
Skill Gap Analysis Service
POST /api/skill-gap/analyze  — candidate flow
Runs the 5-stage pipeline against a candidate's resume and returns
a SkillGapAnalysisResponse compatible with the frontend SkillGapResponse type.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resume_model import Resume
from src.models.user_model import User, UserRole
from src.schema.application_schema import (
    SkillGapAnalysisResponse,
    MatchedSkillItemSchema,
    MissingSkillItemSchema,
    ExtraSkillItemSchema,
    RoadmapSkillItemSchema,
    RoadmapPhasesSchema,
)
from src.services.ai_pipeline_service import run_pipeline
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


async def analyze_skill_gap_service(
    db: AsyncSession,
    resume_id: uuid.UUID,
    jd_text: str,
    current_user: User,
) -> SkillGapAnalysisResponse:
    """Run the AI pipeline for a candidate's resume vs a job description."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can run skill gap analysis")

    if not jd_text.strip():
        raise AppException(ErrorCode.INVALID_INPUT, "Job description cannot be empty")

    # Verify resume belongs to this user
    candidate_profile = getattr(current_user, "candidate_profile", None)
    if candidate_profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Candidate profile not found")

    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.candidate_id == candidate_profile.id,
        )
    )
    resume = result.scalar_one_or_none()
    if resume is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Resume not found")

    # Run pipeline
    pipeline_result = await run_pipeline(
        jd_text=jd_text,
        resume_data=resume.resume_data,
    )

    # Map pipeline dataclasses → Pydantic schemas
    matched = [
        MatchedSkillItemSchema(
            name=s.name,
            canonical_id=s.canonical_id,
            match_type=s.match_type,
            confidence=s.confidence,
            category=s.category,
            years=s.years,
            weighted_score=s.weighted_score,
        )
        for s in pipeline_result.matched_skills
    ]

    missing = [
        MissingSkillItemSchema(
            name=s.name,
            canonical_id=s.canonical_id,
            category=s.category,
            computed_weight=s.computed_weight,
            priority_score=s.priority_score,
            section=s.section,
        )
        for s in pipeline_result.missing_skills
    ]

    extra = [
        ExtraSkillItemSchema(
            name=s.name,
            canonical_id=s.canonical_id,
            category=s.category,
        )
        for s in pipeline_result.extra_skills
    ]

    def _roadmap_item(s) -> RoadmapSkillItemSchema:
        return RoadmapSkillItemSchema(
            name=s.name,
            canonical_id=s.canonical_id,
            category=s.category,
            domain=s.domain,
            is_prerequisite=s.is_prerequisite,
            priority_score=s.priority_score,
            subtopics=s.subtopics,
        )

    roadmap = RoadmapPhasesSchema(
        phase_1_core=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_1_core],
        phase_2_primary=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_2_primary],
        phase_3_advanced=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_3_advanced],
    )

    match_pct = round(
        len(matched) / max(pipeline_result.total_jd_skills, 1) * 100, 1
    )

    return SkillGapAnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        resume_id=str(resume_id),
        match_percentage=match_pct,
        total_jd_skills=pipeline_result.total_jd_skills,
        hard_skill_match=pipeline_result.hard_skill_match,
        soft_skill_match=pipeline_result.soft_skill_match,
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
        gap_report=pipeline_result.gap_report,
        roadmap=roadmap,
        ontology_version="ollama-bge-v1",
    )
