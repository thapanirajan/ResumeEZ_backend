from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db


candidate_dashbaord_router = APIRouter(tags=["Candidate Dashbaord"])


@candidate_dashbaord_router.get("/")
async def get_dashbaord_data(db: AsyncSession = Depends(get_db)):
    pass
