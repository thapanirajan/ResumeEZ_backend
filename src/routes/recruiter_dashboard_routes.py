from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models.user_model import User
from src.schema.recruiter_dashboard_schema import RecruiterDashboardResponse
from src.services.recruiter_dashboard_service import get_recruiter_dashboard_data

recruiter_dashboard_router = APIRouter(tags=["Recruiter Dashboard"])


@recruiter_dashboard_router.get(
    "/",
    response_model=RecruiterDashboardResponse,
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_recruiter_dashboard_data(db, current_user)
