import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def get_candidate_resume_count(db: AsyncSession, time: datetime.datetime) -> dict:
    pass
    # Payload: db session , candidate id from middleware,
    # check role (must be JOB_SEEKER)
    # check if candidate is valid or not
    # join tables to get the number of resume candidate has created
    # return candidate resume count