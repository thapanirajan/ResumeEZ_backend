import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from src.config.base import Base


class UserRole(enum.Enum):
    JOB_SEEKER = "JOB_SEEKER"
    RECRUITER = "RECRUITER"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=True)
    role = Column(Enum(UserRole), nullable=True)
    is_email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
    otp = Column(String, nullable=True)
    otp_expires = Column(DateTime, nullable=True)

    candidate = relationship("Candidate", back_populates="user", uselist=False)
    recruiter = relationship("Recruiter", back_populates="user", uselist=False)
    email_verifications = relationship("EmailVerification", back_populates="user")
    password_resets = relationship("PasswordResetToken", back_populates="user")
