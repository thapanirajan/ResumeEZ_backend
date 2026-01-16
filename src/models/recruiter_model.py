from __future__ import annotations

import uuid
from typing import List, TYPE_CHECKING

from sqlalchemy import (String, ForeignKey)
from sqlalchemy.dialects.postgresql.base import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.user_model import User
    from src.models.job_model import Job



class RecruiterProfile(Base):
    __tablename__ = "recruiter_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        unique=True
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    user: Mapped[User] = relationship(back_populates="recruiter_profile")

    jobs: Mapped[List[Job]] = relationship(
        back_populates="recruiter",
        cascade="all, delete-orphan"
    )
