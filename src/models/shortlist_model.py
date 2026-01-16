from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (DateTime, ForeignKey, Enum)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.candidate_profile_model import CandidateProfile
    from src.models.job_model import Job


class ResumeStatus(enum.Enum):
    PENDING = "PENDING"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"


class Shortlist(Base):
    __tablename__ = "shortlists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id")
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id")
    )

    status: Mapped[ResumeStatus] = mapped_column(
        Enum(ResumeStatus, name="resume_status"),
        default=ResumeStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="shortlists")
    candidate: Mapped[CandidateProfile] = relationship()
