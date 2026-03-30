import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.application_schema import SkillGapAnalysisResponse
from src.services.skill_gap_service import analyze_skill_gap_service

skill_gap_router = APIRouter(tags=["Skill Gap"])


class SkillGapAnalyzeRequest(BaseModel):
    resume_id: uuid.UUID
    jd_text: str


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
