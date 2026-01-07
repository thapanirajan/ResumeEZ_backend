import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.orm import relationship
from src.config.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recruiter_id = Column(String, ForeignKey("recruiters.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String)
    required_skills = Column(Text)
    experience_required = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    recruiter = relationship("Recruiter", back_populates="jobs")
    hr_resumes = relationship("HRUploadedResume", back_populates="job")
