"""
Skill Gap Analysis Service
POST /api/skill-gap/analyze  — candidate flow
Runs the 5-stage pipeline against a candidate's resume and returns
a SkillGapAnalysisResponse compatible with the frontend SkillGapResponse type.

Also provides:
  - history listing (GET /api/skill-gap/history)
  - per-report detail (GET /api/skill-gap/history/{report_id})
  - roadmap retrieval + progress update (GET/PATCH /api/skill-gap/roadmap/{roadmap_id})
"""

from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.resume_model import Resume
from src.models.user_model import User, UserRole
from src.models.skill_gap_report_model import SkillGapReport
from src.models.learning_roadmap_model import LearningRoadmap
from src.schema.application_schema import (
    SkillGapAnalysisResponse,
    MatchedSkillItemSchema,
    MissingSkillItemSchema,
    ExtraSkillItemSchema,
    RoadmapSkillItemSchema,
    RoadmapPhasesSchema,
    SkillGapReportListItem,
    SkillGapReportDetail,
    LearningRoadmapResponse,
)
from src.services.ai_pipeline_service import run_pipeline
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


# ─── helpers ──────────────────────────────────────────────────────────────────

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


def _skill_item_to_dict(s) -> dict:
    """Convert a Pydantic schema to a plain dict for JSONB storage."""
    return s.model_dump()


NodeStatus = Literal["not_started", "in_progress", "done"]


# ─── analyze & persist ────────────────────────────────────────────────────────

async def analyze_skill_gap_service(
    db: AsyncSession,
    resume_id: uuid.UUID,
    jd_text: str,
    current_user: User,
) -> SkillGapAnalysisResponse:
    """Run the AI pipeline for a candidate's resume vs a job description
    and persist the result + roadmap to the database."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can run skill gap analysis")

    if not jd_text.strip():
        raise AppException(ErrorCode.INVALID_INPUT, "Job description cannot be empty")

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

    roadmap_schema = RoadmapPhasesSchema(
        phase_1_core=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_1_core],
        phase_2_primary=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_2_primary],
        phase_3_advanced=[_roadmap_item(s) for s in pipeline_result.roadmap.phase_3_advanced],
    )

    match_pct = round(
        len(matched) / max(pipeline_result.total_jd_skills, 1) * 100, 1
    )

    # Persist the report
    report = SkillGapReport(
        candidate_id=candidate_profile.id,
        resume_id=resume_id,
        jd_text=jd_text,
        match_percentage=match_pct,
        total_jd_skills=pipeline_result.total_jd_skills,
        hard_skill_match=pipeline_result.hard_skill_match,
        soft_skill_match=pipeline_result.soft_skill_match,
        matched_skills=[_skill_item_to_dict(s) for s in matched],
        missing_skills=[_skill_item_to_dict(s) for s in missing],
        extra_skills=[_skill_item_to_dict(s) for s in extra],
        gap_report=pipeline_result.gap_report,
        ontology_version="ollama-bge-v1",
    )
    db.add(report)
    await db.flush()  # get report.id without committing

    # Persist the roadmap
    roadmap_record = LearningRoadmap(
        report_id=report.id,
        candidate_id=candidate_profile.id,
        phase_1_core=[_skill_item_to_dict(s) for s in roadmap_schema.phase_1_core],
        phase_2_primary=[_skill_item_to_dict(s) for s in roadmap_schema.phase_2_primary],
        phase_3_advanced=[_skill_item_to_dict(s) for s in roadmap_schema.phase_3_advanced],
        skill_progress={},
    )
    db.add(roadmap_record)
    await db.commit()
    await db.refresh(report)
    await db.refresh(roadmap_record)

    return SkillGapAnalysisResponse(
        analysis_id=str(report.id),
        resume_id=str(resume_id),
        roadmap_id=str(roadmap_record.id),
        match_percentage=match_pct,
        total_jd_skills=pipeline_result.total_jd_skills,
        hard_skill_match=pipeline_result.hard_skill_match,
        soft_skill_match=pipeline_result.soft_skill_match,
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
        gap_report=pipeline_result.gap_report,
        roadmap=roadmap_schema,
        ontology_version="ollama-bge-v1",
    )


# ─── history ──────────────────────────────────────────────────────────────────

async def get_skill_gap_history_service(
    db: AsyncSession,
    current_user: User,
) -> list[SkillGapReportListItem]:
    """Return all past skill gap reports for the current candidate, newest first."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can view skill gap history")

    candidate_profile = getattr(current_user, "candidate_profile", None)
    if candidate_profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Candidate profile not found")

    stmt = (
        select(SkillGapReport)
        .where(SkillGapReport.candidate_id == candidate_profile.id)
        .order_by(SkillGapReport.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    # Collect roadmap ids in one query
    report_ids = [r.id for r in rows]
    roadmap_map: dict[uuid.UUID, uuid.UUID] = {}
    if report_ids:
        rm_stmt = select(LearningRoadmap.id, LearningRoadmap.report_id).where(
            LearningRoadmap.report_id.in_(report_ids)
        )
        for rm_id, rpt_id in (await db.execute(rm_stmt)).all():
            roadmap_map[rpt_id] = rm_id

    # Collect resume titles in one query
    resume_ids = list({r.resume_id for r in rows})
    resume_titles: dict[uuid.UUID, str] = {}
    if resume_ids:
        res_stmt = select(Resume.id, Resume.title).where(Resume.id.in_(resume_ids))
        for res_id, title in (await db.execute(res_stmt)).all():
            resume_titles[res_id] = title

    return [
        SkillGapReportListItem(
            id=r.id,
            resume_id=r.resume_id,
            resume_title=resume_titles.get(r.resume_id, "Untitled Resume"),
            match_percentage=r.match_percentage,
            total_jd_skills=r.total_jd_skills,
            roadmap_id=roadmap_map.get(r.id),
            created_at=r.created_at,
        )
        for r in rows
    ]


# ─── report detail ────────────────────────────────────────────────────────────

async def get_skill_gap_report_service(
    db: AsyncSession,
    report_id: uuid.UUID,
    current_user: User,
) -> SkillGapReportDetail:
    """Return a single persisted skill gap report (with roadmap_id)."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can view skill gap reports")

    candidate_profile = getattr(current_user, "candidate_profile", None)
    if candidate_profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Candidate profile not found")

    stmt = select(SkillGapReport).where(
        SkillGapReport.id == report_id,
        SkillGapReport.candidate_id == candidate_profile.id,
    )
    report = (await db.execute(stmt)).scalar_one_or_none()
    if report is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Skill gap report not found")

    # Get roadmap id
    rm_stmt = select(LearningRoadmap.id).where(LearningRoadmap.report_id == report_id)
    roadmap_id = (await db.execute(rm_stmt)).scalar_one_or_none()

    # Get resume title
    res_stmt = select(Resume.title).where(Resume.id == report.resume_id)
    resume_title = (await db.execute(res_stmt)).scalar_one_or_none() or "Untitled Resume"

    return SkillGapReportDetail(
        id=report.id,
        resume_id=report.resume_id,
        resume_title=resume_title,
        match_percentage=report.match_percentage,
        total_jd_skills=report.total_jd_skills,
        hard_skill_match=report.hard_skill_match,
        soft_skill_match=report.soft_skill_match,
        matched_skills=[MatchedSkillItemSchema(**s) for s in report.matched_skills],
        missing_skills=[MissingSkillItemSchema(**s) for s in report.missing_skills],
        extra_skills=[ExtraSkillItemSchema(**s) for s in report.extra_skills],
        gap_report=report.gap_report,
        ontology_version=report.ontology_version,
        roadmap_id=roadmap_id,
        created_at=report.created_at,
    )


# ─── roadmap retrieval ────────────────────────────────────────────────────────

async def get_roadmap_service(
    db: AsyncSession,
    roadmap_id: uuid.UUID,
    current_user: User,
) -> LearningRoadmapResponse:
    """Return a learning roadmap (including current skill_progress) by id."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can view roadmaps")

    candidate_profile = getattr(current_user, "candidate_profile", None)
    if candidate_profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Candidate profile not found")

    stmt = select(LearningRoadmap).where(
        LearningRoadmap.id == roadmap_id,
        LearningRoadmap.candidate_id == candidate_profile.id,
    )
    roadmap = (await db.execute(stmt)).scalar_one_or_none()
    if roadmap is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Roadmap not found")

    return LearningRoadmapResponse(
        id=roadmap.id,
        report_id=roadmap.report_id,
        phase_1_core=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_1_core],
        phase_2_primary=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_2_primary],
        phase_3_advanced=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_3_advanced],
        skill_progress=roadmap.skill_progress or {},
        created_at=roadmap.created_at,
        updated_at=roadmap.updated_at,
    )


# ─── progress update ──────────────────────────────────────────────────────────

async def update_roadmap_progress_service(
    db: AsyncSession,
    roadmap_id: uuid.UUID,
    skill_progress: dict[str, str],
    current_user: User,
) -> LearningRoadmapResponse:
    """Persist updated skill_progress for a roadmap."""

    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can update roadmap progress")

    candidate_profile = getattr(current_user, "candidate_profile", None)
    if candidate_profile is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Candidate profile not found")

    stmt = select(LearningRoadmap).where(
        LearningRoadmap.id == roadmap_id,
        LearningRoadmap.candidate_id == candidate_profile.id,
    )
    roadmap = (await db.execute(stmt)).scalar_one_or_none()
    if roadmap is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Roadmap not found")

    valid_statuses = {"not_started", "in_progress", "done"}
    for status in skill_progress.values():
        if status not in valid_statuses:
            raise AppException(
                ErrorCode.INVALID_INPUT,
                f"Invalid status '{status}'. Must be one of: {valid_statuses}",
            )

    roadmap.skill_progress = skill_progress
    await db.commit()
    await db.refresh(roadmap)

    return LearningRoadmapResponse(
        id=roadmap.id,
        report_id=roadmap.report_id,
        phase_1_core=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_1_core],
        phase_2_primary=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_2_primary],
        phase_3_advanced=[RoadmapSkillItemSchema(**s) for s in roadmap.phase_3_advanced],
        skill_progress=roadmap.skill_progress,
        created_at=roadmap.created_at,
        updated_at=roadmap.updated_at,
    )
