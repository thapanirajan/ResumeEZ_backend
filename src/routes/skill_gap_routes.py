import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.application_schema import (
    LearningRoadmapResponse,
    RoadmapProgressUpdateSchema,
    SkillGapAnalysisResponse,
    SkillGapReportDetail,
    SkillGapReportListItem,
)
from src.services.skill_gap_service import (
    analyze_skill_gap_service,
    get_roadmap_service,
    get_skill_gap_history_service,
    get_skill_gap_report_service,
    update_roadmap_progress_service,
)

skill_gap_router = APIRouter(tags=["Skill Gap"])


class SkillGapAnalyzeRequest(BaseModel):
    resume_id: uuid.UUID
    jd_text: str


# ─── Analyze ──────────────────────────────────────────────────────────────────

@skill_gap_router.post(
    "/analyze",
    response_model=SkillGapAnalysisResponse,
)
async def analyze_skill_gap(
    payload: SkillGapAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await analyze_skill_gap_service(
        db=db,
        resume_id=payload.resume_id,
        jd_text=payload.jd_text,
        current_user=current_user,
    )


# ─── History ──────────────────────────────────────────────────────────────────

@skill_gap_router.get(
    "/history",
    response_model=list[SkillGapReportListItem],
)
async def list_skill_gap_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all past skill gap analyses for the current candidate, newest first."""
    return await get_skill_gap_history_service(db=db, current_user=current_user)


@skill_gap_router.get(
    "/history/{report_id}",
    response_model=SkillGapReportDetail,
)
async def get_skill_gap_report(
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single persisted skill gap report by id."""
    return await get_skill_gap_report_service(
        db=db, report_id=report_id, current_user=current_user
    )


# ─── Roadmap ──────────────────────────────────────────────────────────────────

@skill_gap_router.get(
    "/roadmap/{roadmap_id}",
    response_model=LearningRoadmapResponse,
)
async def get_roadmap(
    roadmap_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a learning roadmap with current skill progress."""
    return await get_roadmap_service(
        db=db, roadmap_id=roadmap_id, current_user=current_user
    )


@skill_gap_router.patch(
    "/roadmap/{roadmap_id}/progress",
    response_model=LearningRoadmapResponse,
)
async def update_roadmap_progress(
    roadmap_id: uuid.UUID,
    payload: RoadmapProgressUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist the full skill_progress map for a roadmap."""
    return await update_roadmap_progress_service(
        db=db,
        roadmap_id=roadmap_id,
        skill_progress=payload.skill_progress,
        current_user=current_user,
    )
