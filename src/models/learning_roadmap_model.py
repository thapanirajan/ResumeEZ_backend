from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (DateTime, ForeignKey)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.candidate_profile_model import CandidateProfile



class LearningRoadmap(Base):
    __tablename__ = "learning_roadmaps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidate_profiles.id")
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id")
    )

    recommended_skills: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    candidate: Mapped[CandidateProfile] = relationship(
        back_populates="learning_roadmaps"
    )
