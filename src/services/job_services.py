from sqlalchemy import Select, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.NLP_services.text_normalizer import normalize_text
from src.models import Job, RecruiterProfile
from src.schema.jobs_schema import JobCreateSchema
from src.utils.exceptions import AppException


async def handle_create_job(db: AsyncSession, data: JobCreateSchema, recruiter_id: UUID):
    """
    Creates a job in DRAFT state with auto-extracted skills.
    """
    result = await db.execute(
        Select(RecruiterProfile)
        .where(RecruiterProfile.id == recruiter_id)
    )

    recruiter = result.scalar_one_or_none()

    if not recruiter:
        raise AppException(
            code="BAD_REQUEST",
            message="Unable to find recruiter profile",
            status_code=status.HTTP_404_NOT_FOUND
        )

    normalized_description = normalize_text(data.description)

    job = Job(
        title=data.title,
        description=normalized_description,
        recruiter_id=recruiter_id,
    )

    print("-----job-----")
    print(job)

    # db.add(job)
    #
    # await db.commit()
    # await db.refresh(job)


async def handle_update_job(db: AsyncSession, data: JobCreateSchema, recruiter_id: str):
    pass


async def parse_jd_service(job_id: str, jd_text: str, db: AsyncSession):
    pass


def extract_skills(description: str | None) -> dict:
    """
    Temporary skill extractor.
    Replace with NLP / AI later.
    """
    if not description:
        return {
            "must_have": [],
            "good_to_have": [],
            "experience": None
        }
    skills = []

    text = description.lower()
