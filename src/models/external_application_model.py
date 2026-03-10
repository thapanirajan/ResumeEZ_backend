from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.job_model import Job


class ExternalApplicationSource(enum.Enum):
    EMAIL = "EMAIL"
    LINKEDIN = "LINKEDIN"
    REFERRAL = "REFERRAL"
    OFFLINE = "OFFLINE"
    OTHER = "OTHER"


class ExternalApplicationStatus(enum.Enum):
    PENDING = "PENDING"
    REVIEWING = "REVIEWING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ExternalApplication(Base):
    __tablename__ = "external_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=False,
    )

    candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)

    candidate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    source: Mapped[ExternalApplicationSource] = mapped_column(
        Enum(ExternalApplicationSource),
        default=ExternalApplicationSource.OTHER,
        nullable=False,
    )

    resume_file_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    resume_filename: Mapped[str] = mapped_column(String(512), nullable=False)

    status: Mapped[ExternalApplicationStatus] = mapped_column(
        Enum(ExternalApplicationStatus),
        default=ExternalApplicationStatus.PENDING,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ---------------- RELATIONSHIPS ----------------

    job: Mapped["Job"] = relationship(back_populates="external_applications")
