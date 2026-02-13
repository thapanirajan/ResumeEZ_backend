from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.config.db import get_db

skill_gap_router = APIRouter(tags=["Skill Gap"])

@skill_gap_router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(
        db: AsyncSession = Depends(get_db)
):
    # ------------- 1. check if the resume id send from frontend exist or not ------------------
    # ------------- 2. Normalize job description -----------------------------------------------
    # ------------- 3. Normalize resume  data  -----------------------------------------------
    # --------------4. Extract skills from both resume and job description ---------------------
    # --------------5. Compare skills and find missing skill in resume -------------------------
    # --------------6. Based on the missing skills generate roadmap -----------------------------
    pass


