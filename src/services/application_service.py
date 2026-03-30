import asyncio
import io
import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.models.candidate_profile_model import CandidateProfile
from src.models.external_application_model import ExternalApplication
from src.models.job_application_model import JobApplication, ApplicationStatus
from src.models.job_model import Job, JobStatus
from src.models.resume_model import Resume
from src.models.user_model import User, UserRole
from src.schema.application_schema import (
    ApplicationCreateSchema,
    ApplicationResponse,
    ApplicationDetailResponse,
    ApplicationResumeResponse,
    ApplicationScoreItem,
    ExternalApplicationScoreItem,
    ApplicationScoresResponse,
    ApplicationAnalysisSchema,
    MatchedSkillItemSchema,
    MissingSkillItemSchema,
    ExtraSkillItemSchema,
    JobWithApplicantsSchema,
)
from src.services.ai_pipeline_service import run_pipeline, PipelineResult
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


def _get_candidate_profile(current_user: User):
    profile = getattr(current_user, "candidate_profile", None)
    if profile is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Candidate profile not found",
        )
    return profile


def _get_recruiter_profile(current_user: User):
    profile = getattr(current_user, "recruiter_profile", None)
    if profile is None:
        raise AppException(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Recruiter profile not found",
        )
    return profile


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/applications/  — Candidate applies to a job
# ─────────────────────────────────────────────────────────────────────────────
async def apply_to_job_service(
    db: AsyncSession,
    payload: ApplicationCreateSchema,
    current_user: User,
) -> JobApplication:
    # checks if the logged in use is JOB SEEKER or not
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can apply to jobs")

    candidate_profile = _get_candidate_profile(current_user)

    # Verify job exists and is open
    job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.status != JobStatus.OPEN:
        raise AppException(ErrorCode.INVALID_INPUT, "This job is not accepting applications")

    # Verify resume belongs to this candidate
    resume_result = await db.execute(
        select(Resume).where(
            and_(
                Resume.id == payload.resume_id,
                Resume.candidate_id == candidate_profile.id,
            )
        )
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Resume not found")

    application = JobApplication(
        job_id=payload.job_id,
        candidate_id=candidate_profile.id,
        resume_id=payload.resume_id,
        cover_letter=payload.cover_letter,
    )

    db.add(application)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppException(ErrorCode.DUPLICATE_RESOURCE, "You have already applied to this job")

    await db.refresh(application)
    return application


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/me  — Candidate views their own applications
# ─────────────────────────────────────────────────────────────────────────────
async def get_my_applications_service(
    db: AsyncSession,
    current_user: User,
) -> list[JobApplication]:
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can view their applications")

    candidate_profile = _get_candidate_profile(current_user)

    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.candidate_id == candidate_profile.id)
        .order_by(JobApplication.applied_at.desc())
    )
    return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/check/{job_id}  — Has this candidate already applied?
# ─────────────────────────────────────────────────────────────────────────────
async def check_application_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> JobApplication | None:
    if current_user.role != UserRole.JOB_SEEKER:
        raise AppException(ErrorCode.FORBIDDEN, "Only candidates can check applications")

    candidate_profile = _get_candidate_profile(current_user)

    result = await db.execute(
        select(JobApplication).where(
            and_(
                JobApplication.job_id == job_id,
                JobApplication.candidate_id == candidate_profile.id,
            )
        )
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/job/{job_id}  — Recruiter views applications for their job
# ─────────────────────────────────────────────────────────────────────────────
async def get_applications_for_job_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> list[ApplicationDetailResponse]:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can view job applications")

    recruiter_profile = _get_recruiter_profile(current_user)

    # Verify the job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to view these applications")

    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.job_id == job_id)
        .order_by(JobApplication.applied_at.desc())
    )
    applications = list(result.scalars().all())

    # Enrich with candidate name, email, and resume title
    enriched: list[ApplicationDetailResponse] = []
    for app in applications:
        candidate_result = await db.execute(
            select(CandidateProfile).where(CandidateProfile.id == app.candidate_id)
        )
        candidate = candidate_result.scalar_one_or_none()

        print("---------candidate----------")
        print(candidate.__dict__)
        print("---------candidate----------")


        candidate_email: str | None = None
        if candidate:
            user_result = await db.execute(
                select(User).where(User.id == candidate.user_id)
            )
            user = user_result.scalar_one_or_none()
            candidate_email = user.email if user else None

        resume_result = await db.execute(
            select(Resume).where(Resume.id == app.resume_id)
        )
        resume = resume_result.scalar_one_or_none()

        enriched.append(
            ApplicationDetailResponse(
                id=app.id,
                job_id=app.job_id,
                candidate_id=app.candidate_id,
                resume_id=app.resume_id,
                status=app.status,
                cover_letter=app.cover_letter,
                applied_at=app.applied_at,
                updated_at=app.updated_at,
                candidate_name=candidate.full_name,
                candidate_email=candidate_email,
                resume_title=resume.title if resume else None,
            )
        )

    return enriched


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/applications/{application_id}/status  — Recruiter updates status
# ─────────────────────────────────────────────────────────────────────────────
async def update_application_status_service(
    db: AsyncSession,
    application_id: uuid.UUID,
    new_status: ApplicationStatus,
    current_user: User,
) -> JobApplication:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can update application status")

    recruiter_profile = _get_recruiter_profile(current_user)

    result = await db.execute(
        select(JobApplication).where(JobApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Application not found")

    # Verify the job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "You are not authorized to update this application")

    application.status = new_status
    await db.commit()
    await db.refresh(application)
    return application


# ─────────────────────────────────────────────────────────────────────────────
# GET job with all applicants — Job details + each application with
#   full candidate profile and full resume data.
#
# Uses selectinload to fetch all related rows in 3 additional SELECT
# statements (no N+1). Safe for async SQLAlchemy.
#
# Access control: only the recruiter who owns the job can call this.
# ─────────────────────────────────────────────────────────────────────────────
async def get_job_with_applicants_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> JobWithApplicantsSchema:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can view job applicants")

    recruiter_profile = _get_recruiter_profile(current_user)

    # Single query: load the job and eagerly load
    #   job.applications → application.candidate
    #   job.applications → application.resume
    result = await db.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.applications).selectinload(JobApplication.candidate),
            selectinload(Job.applications).selectinload(JobApplication.resume),
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")

    if job.recruiter_id != recruiter_profile.id:
        raise AppException(
            ErrorCode.UNAUTHORIZED_ACCESS,
            "You are not authorized to view applicants for this job",
        )

    return JobWithApplicantsSchema.model_validate(job)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/{application_id}/resume  — Recruiter views CV
# ─────────────────────────────────────────────────────────────────────────────
async def get_application_resume_service(
    db: AsyncSession,
    application_id: uuid.UUID,
    current_user: User,
) -> ApplicationResumeResponse:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can view candidate resumes")

    recruiter_profile = _get_recruiter_profile(current_user)

    # Load application
    app_result = await db.execute(
        select(JobApplication).where(JobApplication.id == application_id)
    )
    application = app_result.scalar_one_or_none()
    if application is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Application not found")

    # Verify the job belongs to this recruiter
    job_result = await db.execute(select(Job).where(Job.id == application.job_id))
    job = job_result.scalar_one_or_none()
    if job is None or job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "Not authorized to view this resume")

    # Load resume
    resume_result = await db.execute(
        select(Resume).where(Resume.id == application.resume_id)
    )
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Resume not found")

    return ApplicationResumeResponse(
        resume_id=resume.id,
        resume_title=resume.title,
        resume_data=resume.resume_data,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction from uploaded resume files (PDF / DOCX)
# ─────────────────────────────────────────────────────────────────────────────

def _keywords(text: str) -> set[str]:
    """Kept as utility for other parts of the codebase."""
    stop = frozenset({"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
                      "of", "with", "by", "from", "is", "are", "was", "were", "be", "been"})
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in stop}


async def _extract_text_from_url(url: str, filename: str) -> str:
    """Download a resume file from a URL and return its plain text."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
    except Exception:
        return ""

    fname = filename.lower()
    try:
        if fname.endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content), strict=False)
            return " ".join(page.extract_text() or "" for page in reader.pages)
        elif fname.endswith(".docx"):
            import docx
            doc = docx.Document(io.BytesIO(content))
            return " ".join(para.text for para in doc.paragraphs)
    except Exception:
        pass
    return ""


def _pipeline_result_to_analysis_schema(result: PipelineResult) -> ApplicationAnalysisSchema:
    """Convert PipelineResult dataclass to Pydantic schema."""
    return ApplicationAnalysisSchema(
        ats_score=result.ats_score,
        skills_score=result.skills_score,
        experience_score=result.experience_score,
        education_score=result.education_score,
        matched_skills=[
            MatchedSkillItemSchema(
                name=s.name,
                canonical_id=s.canonical_id,
                match_type=s.match_type,
                confidence=s.confidence,
                category=s.category,
                years=s.years,
                weighted_score=s.weighted_score,
            )
            for s in result.matched_skills
        ],
        missing_skills=[
            MissingSkillItemSchema(
                name=s.name,
                canonical_id=s.canonical_id,
                category=s.category,
                computed_weight=s.computed_weight,
                priority_score=s.priority_score,
                section=s.section,
            )
            for s in result.missing_skills
        ],
        extra_skills=[
            ExtraSkillItemSchema(
                name=s.name,
                canonical_id=s.canonical_id,
                category=s.category,
            )
            for s in result.extra_skills
        ],
        gap_report=result.gap_report,
        reasoning=result.reasoning,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/applications/job/{job_id}/ai-scores  — Score all applicants
# ─────────────────────────────────────────────────────────────────────────────
async def score_applications_for_job_service(
    db: AsyncSession,
    job_id: uuid.UUID,
    current_user: User,
) -> ApplicationScoresResponse:
    if current_user.role != UserRole.RECRUITER:
        raise AppException(ErrorCode.FORBIDDEN, "Only recruiters can run AI scoring")

    recruiter_profile = _get_recruiter_profile(current_user)

    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    if job is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Job not found")
    if job.recruiter_id != recruiter_profile.id:
        raise AppException(ErrorCode.UNAUTHORIZED_ACCESS, "Not authorized")

    now = datetime.now(timezone.utc)

    # Limit concurrent Ollama calls to avoid overloading the local model server
    semaphore = asyncio.Semaphore(2)

    # ── Platform applications (JSON resume data) ──────────────────────────────
    app_result = await db.execute(
        select(JobApplication).where(JobApplication.job_id == job_id)
    )
    applications = list(app_result.scalars().all())

    # Pre-load resumes in one query
    resume_ids = [a.resume_id for a in applications if a.resume_id]
    resume_map: dict = {}
    if resume_ids:
        res_result = await db.execute(select(Resume).where(Resume.id.in_(resume_ids)))
        for r in res_result.scalars().all():
            resume_map[r.id] = r

    async def _score_platform(app: JobApplication):
        resume = resume_map.get(app.resume_id)
        if not resume:
            return ApplicationScoreItem(application_id=app.id, score=0, analysis=None)
        async with semaphore:
            pipeline_result = await run_pipeline(
                jd_text=job.description,
                resume_data=resume.resume_data,
            )
        analysis = _pipeline_result_to_analysis_schema(pipeline_result)
        app.ai_score = pipeline_result.ats_score
        app.ai_analysis = analysis.model_dump()
        app.ai_scored_at = now
        return ApplicationScoreItem(
            application_id=app.id,
            score=pipeline_result.ats_score,
            analysis=analysis,
        )

    scores: list[ApplicationScoreItem] = await asyncio.gather(
        *[_score_platform(app) for app in applications]
    )

    # ── External applications (uploaded PDF/DOCX files) ───────────────────────
    ext_result = await db.execute(
        select(ExternalApplication).where(ExternalApplication.job_id == job_id)
    )
    external_applications = list(ext_result.scalars().all())

    async def _score_external(ext: ExternalApplication):
        text = await _extract_text_from_url(ext.resume_file_url, ext.resume_filename)
        if ext.notes:
            text = f"{text} {ext.notes}"
        async with semaphore:
            pipeline_result = await run_pipeline(
                jd_text=job.description,
                resume_text=text if text.strip() else None,
            )
        analysis = _pipeline_result_to_analysis_schema(pipeline_result)
        ext.ai_score = pipeline_result.ats_score
        ext.ai_analysis = analysis.model_dump()
        ext.ai_scored_at = now
        return ExternalApplicationScoreItem(
            external_application_id=ext.id,
            score=pipeline_result.ats_score,
            analysis=analysis,
        )

    external_scores: list[ExternalApplicationScoreItem] = await asyncio.gather(
        *[_score_external(ext) for ext in external_applications]
    )

    await db.commit()

    return ApplicationScoresResponse(scores=list(scores), external_scores=list(external_scores))
