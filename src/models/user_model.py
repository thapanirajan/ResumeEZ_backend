import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (String, Boolean, DateTime, func, Enum)

from src.config.base import Base

if TYPE_CHECKING:
    from src.models.recruiter_model import RecruiterProfile
    from src.models.candidate_profile_model import CandidateProfile


class UserRole(enum.Enum):
    JOB_SEEKER = "JOB_SEEKER"
    RECRUITER = "RECRUITER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    otp_code: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    recruiter_profile: Mapped["RecruiterProfile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    candidate_profile: Mapped["CandidateProfile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
