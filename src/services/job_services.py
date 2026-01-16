from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job
from src.schema.jobs_schema import JobCreateSchema


async def handle_create_job(db: AsyncSession, data: JobCreateSchema, recruiter_id: str):
    job = Job(
        title=data.title,
        description_raw=data.description_raw,
        recruiter_id=recruiter_id,
    )

    print("-----job-----")
    print(job)

    # db.add(job)
    #
    # await db.commit()
    # await db.refresh(job)

async def handle_update_job(db:AsyncSession, data:JobCreateSchema,recruiter_id: str):
    pass




async def parse_jd_service(job_id: str, jd_text: str, db: AsyncSession):
    pass
