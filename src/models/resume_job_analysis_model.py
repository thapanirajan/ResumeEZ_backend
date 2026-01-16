from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (DateTime, ForeignKey, Float)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base
from src.models.job_model import Job
from src.models.resume_model import Resume

# AI output
class ResumeJobAnalysis(Base):
    __tablename__ = "resume_job_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id")
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id")
    )

    match_score: Mapped[float | None] = mapped_column(Float)
    matched_skills: Mapped[dict | None] = mapped_column(JSONB)
    missing_skills: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    resume: Mapped[Resume] = relationship(back_populates="analyses")
    job: Mapped[Job] = relationship(back_populates="analyses")
