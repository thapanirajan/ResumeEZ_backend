from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import (String, DateTime, ForeignKey, Text)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models import RecruiterProfile
    from src.models.resume_job_analysis_model import ResumeJobAnalysis
    from src.models.shortlist_model import Shortlist


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recruiter_profiles.id")
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    #JD raw text, JD copy and paste
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # will be store after extracting required skills
    required_skills: Mapped[dict | None] = mapped_column(JSONB)

    # JD file PDF/DOCS
    jd_file_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default="DRAFT") # DRAFT, ACTIVE, CLOSED, ARCHIVED
    processing_status: Mapped[str] = mapped_column(String(20), default="PROCESSING") # PROCESSING, COMPLETED, FAILED
    experience_level: Mapped[str | None] = mapped_column(String(100), nullable=True)
    education: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    recruiter: Mapped[RecruiterProfile] = relationship(back_populates="jobs")

    analyses: Mapped[list[ResumeJobAnalysis]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan"
    )

    shortlists: Mapped[List[Shortlist]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan"
    )
