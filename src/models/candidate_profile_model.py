from __future__ import annotations

import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import (String, ForeignKey, Integer)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.user_model import User
    from src.models.resume_model import Resume


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        unique=True
    )

    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    current_role: Mapped[str | None] = mapped_column(String(255))
    experience_years: Mapped[int | None] = mapped_column(Integer)

    bio: Mapped[str | None] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(255))
    skills: Mapped[list | None] = mapped_column(JSONB)
    is_profile_complete: Mapped[bool] = mapped_column(default=False)
    profile_score: Mapped[int | None] = mapped_column(Integer)
    is_public: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="candidate_profile")

    resumes: Mapped[List[Resume]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan"
    )
