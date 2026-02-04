from sqlalchemy import Select, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.NLP_services.text_normalizer import normalize_text
from src.models import Job, RecruiterProfile
from src.schema.jobs_schema import JobCreateSchema
from src.utils.exceptions import AppException
from src.utils.error_code import ErrorCode


from src.services.file_extraction_service import FileExtractionService
from src.NLP_services.skill_extractor import SkillExtractorService
from datetime import timedelta
from difflib import SequenceMatcher
from sqlalchemy import func


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
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Unable to find recruiter profile",
        )

    # 1. Duplicate Detection
    if not data.confirm_check:
        # Fetch jobs from last 30 days
        thirty_days_ago = func.now() - timedelta(days=30)
        recent_jobs_result = await db.execute(
            Select(Job.title)
            .where(Job.recruiter_id == recruiter_id, Job.created_at >= thirty_days_ago)
        )
        recent_titles = recent_jobs_result.scalars().all()
        
        for recent_title in recent_titles:
            similarity = SequenceMatcher(None, data.title.lower(), recent_title.lower()).ratio()
            if similarity > 0.8:
                 raise AppException(
                    code=ErrorCode.DUPLICATE_RESOURCE,
                    message=f"Similar job title '{recent_title}' exists from last 30 days. Set confirm_check=True to proceed.",
                )

    # 2. Content Acquisition
    description_text = ""
    if data.description:
        description_text = data.description
    elif data.jd_file_url:
        # Extract from URL
        # Note: In a real async app, run this in executor to avoid blocking
        try:
            description_text = FileExtractionService.extract_from_url(data.jd_file_url)
        except Exception as e:
             raise AppException(
                code=ErrorCode.INVALID_INPUT,
                message=f"Failed to extract text from file: {str(e)}",
            )
    
    if len(description_text) < 10:
         raise AppException(
            code=ErrorCode.INVALID_INPUT,
            message="Job description content is too short or empty.",
        )

    normalized_description = normalize_text(description_text)

    # 2. NLP Processing
    extracted_data = {}
    processing_status = "COMPLETED"
    processing_error = None
    
    try:
        extracted_data = SkillExtractorService.extract_details(normalized_description)
    except Exception as e:
        processing_status = "FAILED"
        processing_error = str(e)
        # We still save the job but with failed status
    
    # 3. Data Persistence
    job = Job(
        title=data.title,
        description=normalized_description,
        recruiter_id=recruiter_id,
        jd_file_url=data.jd_file_url,
        status="DRAFT", # Default
        processing_status=processing_status,
        processing_error=processing_error,
        required_skills=extracted_data.get("skills"),
        experience_level=extracted_data.get("experience_level"),
        education=extracted_data.get("education")
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    return job


async def handle_update_job(db: AsyncSession, data: JobCreateSchema, recruiter_id: str):
    pass


async def parse_jd_service(job_id: str, jd_text: str, db: AsyncSession):
    pass

