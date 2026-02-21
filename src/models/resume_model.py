from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (DateTime, ForeignKey, Text, String)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.candidate_profile_model import CandidateProfile


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id")
    )

    # -----------------Resume content-------------
    title: Mapped[Text] = mapped_column(
        String(255),
        nullable=False
    )

    resume_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )


    # ---------------------METADATA---------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )


    # --------------------RELATIONSHIP-----------------

    candidate: Mapped[CandidateProfile] = relationship(back_populates="resumes")
