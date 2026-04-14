from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.candidate_dashboard_schema import CandidateDashboardResponse
from src.services.candidate_dashboard_service import get_candidate_dashboard_service

candidate_dashbaord_router = APIRouter(tags=["Candidate Dashboard"])


@candidate_dashbaord_router.get(
    "/",
    response_model=CandidateDashboardResponse,
)
async def get_candidate_dashboard_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Single endpoint that returns every piece of data required to render
    the candidate dashboard — KPIs, chart datasets, and recent activity.
    """
    return await get_candidate_dashboard_service(db, current_user)
