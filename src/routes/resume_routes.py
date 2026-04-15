import io
import json
import re
import traceback

import PyPDF2
import docx
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from src.config.db import get_db
from src.middlewares.auth_middleware import require_role
from src.models import User, Resume
from src.models.user_model import UserRole
from src.schema.resume_schema import (
    ResumeCreateSchema,
    ResumeUpdateSchema,
    ResumeResponseSchema,
    CandidateResumeListResponseSchema,
)

from src.services.groq_service import extract_resume_json
from src.services.resume_service import ResumeService
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException
from src.utils.permissions import ownership_required


# ─── Text extraction helpers ──────────────────────────────────────────────────

def _extract_text_from_pdf(data: bytes) -> str:
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_text_from_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(para.text for para in doc.paragraphs)


def _normalize_date(value: str) -> str:
    """Convert common date formats to YYYY-MM or 'Present'."""
    if not value:
        return ""
    v = value.strip()
    if v.lower() in ("present", "current", "now"):
        return "Present"
    # Already YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", v):
        return v
    # YYYY only → YYYY-01
    if re.match(r"^\d{4}$", v):
        return f"{v}-01"
    # Month YYYY or Month, YYYY
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"([a-zA-Z]+)[.,\s]+(\d{4})", v)
    if m:
        month = month_map.get(m.group(1).lower()[:3], "01")
        return f"{m.group(2)}-{month}"
    return v


def _normalize_resume_dates(data: dict) -> dict:
    """Walk experience and education arrays and normalise their date fields."""
    for exp in data.get("experience", []):
        exp["startDate"] = _normalize_date(exp.get("startDate", ""))
        exp["endDate"] = _normalize_date(exp.get("endDate", ""))
    for edu in data.get("education", []):
        edu["startDate"] = _normalize_date(edu.get("startDate", ""))
        edu["endDate"] = _normalize_date(edu.get("endDate", ""))
    return data


resume_builder_router = APIRouter(tags=["Resume Builder"])

resume_service = ResumeService()


# POST /resumes	Create resume for authenticated candidate
# -----------------Create Resume -----------------------------------------------
@resume_builder_router.post(
    "",
    response_model=ResumeResponseSchema,
    status_code=status.HTTP_201_CREATED
)
async def create_resume(
        payload: ResumeCreateSchema,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER)),
):
    # Ensure profile exists
    if not candidate.candidate_profile:
        raise AppException(
            code=ErrorCode.FORBIDDEN,
            message="Candidate profile not found. Please set your role first."
        )

    #  calling service layer to handle resume create
    resume = await resume_service.create_resume(db, candidate.candidate_profile.id, payload)

    return resume


# ----------------------Get a list of resumes created by logged-in user ------------------------------------------
# GET /resumes	List resumes owned by candidate
@resume_builder_router.get("", response_model=CandidateResumeListResponseSchema, status_code=status.HTTP_200_OK)
async def get_candidate_resumes(
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    if not candidate.candidate_profile:
        return {
            "success": True,
            "message": "No candidate profile found for this user.",
            "data": [],
        }

    resumes = await resume_service.get_resumes_by_candidate_id(db, candidate.candidate_profile.id)

    return {
        "success": True,
        "message": "Candidate resumes fetched successfully.",
        "data": resumes,
    }


# -----------------------Get resume details by id --------------------------------------
# GET /resumes/{id}	Get single resume (ownership enforced)
@resume_builder_router.get("/{resource_id}", response_model=ResumeResponseSchema, status_code=status.HTTP_200_OK)
async def get_resume_by_id(
        resource_id: UUID,
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    if not candidate.candidate_profile:
        raise AppException(ErrorCode.FORBIDDEN, "Candidate profile not found")

    resume = await resume_service.get_resume_by_id(db, resource_id, candidate.candidate_profile.id)
    return resume


# -----------------------------Update resume by id ---------------------------------
# PATCH /resumes/{id}	Partial update
@resume_builder_router.patch("/{resource_id}", status_code=status.HTTP_200_OK)
async def update_resume(
        payload: ResumeUpdateSchema,
        resume: Resume = Depends(
            ownership_required(
                model=Resume,
                owner_field="candidate_id",
                allowed_roles=[UserRole.JOB_SEEKER],
            )
        ),
        db: AsyncSession = Depends(get_db),
):
    await resume_service.update_resume(db, resume.id, resume.candidate_id, payload)

    return {
        "success": True,
        "message": "Resume Updated successfully"
    }


# -----------------Delete resume by id----------------------------------------
# DELETE /resumes/{id}	Delete resume + cascades analyses
@resume_builder_router.delete("/{resource_id}", status_code=status.HTTP_200_OK)
async def delete_resume(
        resume: Resume = Depends(
            ownership_required(
                model=Resume,
                owner_field="candidate_id",
                allowed_roles=[UserRole.JOB_SEEKER],
            )
        ),
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER))
):
    if not candidate.candidate_profile:
        raise AppException(ErrorCode.FORBIDDEN, "Candidate profile not found")

    result = await resume_service.delete_resume(db, resume.id, candidate.candidate_profile.id)
    if not result:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Resume not found")

    return {
        "success": True,
        "message": "Resume Deleted successfully"
    }


# -----------------Import resume from PDF / DOCX ----------------------------------------
# POST /resumes/import
@resume_builder_router.post(
    "/import",
    response_model=ResumeResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def import_resume(
        file: UploadFile = File(...),
        db: AsyncSession = Depends(get_db),
        candidate: User = Depends(require_role(UserRole.JOB_SEEKER)),
):
    try:
        if not candidate.candidate_profile:
            raise AppException(ErrorCode.FORBIDDEN,
                               "Candidate profile not found")

        filename = (file.filename or "").lower()
        if not (filename.endswith(".pdf") or filename.endswith(".docx")):
            raise AppException(ErrorCode.VALIDATION_ERROR,
                               "Only PDF and DOCX files are supported")

        file_bytes = await file.read()
        print(f"[import] file={filename}, size={len(file_bytes)} bytes")

        # Step 1 — extract raw text
        try:
            if filename.endswith(".pdf"):
                raw_text = _extract_text_from_pdf(file_bytes)
            else:
                raw_text = _extract_text_from_docx(file_bytes)
        except Exception as e:
            traceback.print_exc()
            raise AppException(ErrorCode.INTERNAL_SERVER_ERROR,
                               f"Failed to read file: {e}")

        print(f"[import] extracted {len(raw_text)} chars of text")

        if not raw_text.strip():
            raise AppException(ErrorCode.VALIDATION_ERROR,
                               "Could not extract text from the uploaded file")

        # Step 2 — ask Groq to structure the resume
        try:
            json_str = await extract_resume_json(raw_text)
        except Exception as e:
            traceback.print_exc()
            raise AppException(ErrorCode.INTERNAL_SERVER_ERROR,
                               f"AI extraction failed: {e}")

        print(f"[import] Groq returned {len(json_str)} chars")

        # Step 3 — parse JSON (strip markdown code fences if present)
        json_str = re.sub(r"```(?:json)?\s*", "",
                          json_str).strip().rstrip("`").strip()
        try:
            resume_data = json.loads(json_str)
        except json.JSONDecodeError:
            print("[import] Raw Groq response that failed JSON parse:",
                  json_str[:500])
            raise AppException(ErrorCode.INTERNAL_SERVER_ERROR,
                               "AI returned invalid JSON. Please try again.")

        print(f"[import] parsed JSON OK, keys={list(resume_data.keys())}")

        # Step 4 — normalise dates
        resume_data = _normalize_resume_dates(resume_data)

        # Step 5 — pick a title
        candidate_name = resume_data.get("name", "").strip()
        title = f"{candidate_name}'s Resume" if candidate_name else "Imported Resume"
        print(f"[import] saving as '{title}'")

        # Step 6 — save exactly like a builder-created resume
        payload = ResumeCreateSchema(title=title, resume_data=resume_data)
        resume = await resume_service.create_resume(db, candidate.candidate_profile.id, payload)
        print(f"[import] saved resume id={resume.id}")
        return resume

    except AppException:
        raise
    except Exception as e:
        print("--------Error------------", str(e))
        traceback.print_exc()
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR,
                           "Unexpected error during import. Check server logs.")
