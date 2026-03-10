from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.recruiter_model import RecruiterProfile
    from src.models.job_application_model import JobApplication
    from src.models.external_application_model import ExternalApplication


class EmploymentType(enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    INTERNSHIP = "INTERNSHIP"
    CONTRACT = "CONTRACT"
    REMOTE = "REMOTE"


class JobStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    DRAFT = "DRAFT"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    recruiter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recruiter_profiles.id"),
        nullable=False
    )

    # ---------------- BASIC INFO ----------------

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    location: Mapped[str | None] = mapped_column(
        String(255)
    )

    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType),
        nullable=False
    )

    experience_required: Mapped[int | None] = mapped_column(
        Integer
    )

    salary_min: Mapped[int | None] = mapped_column(
        Integer
    )

    salary_max: Mapped[int | None] = mapped_column(
        Integer
    )

    application_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus),
        default=JobStatus.OPEN
    )

    # ---------------- METADATA ----------------

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # ---------------- RELATIONSHIP ----------------

    recruiter: Mapped["RecruiterProfile"] = relationship(
        back_populates="jobs"
    )

    applications: Mapped[list["JobApplication"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )

    external_applications: Mapped[list["ExternalApplication"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
