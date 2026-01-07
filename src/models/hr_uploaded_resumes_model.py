import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from src.config.base import Base


class HRUploadedResume(Base):
    __tablename__ = "hr_uploaded_resumes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_email = Column(String)
    file_path = Column(String, nullable=False)
    resume_text = Column(Text)
    score = Column(Float)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    job = relationship("Job", back_populates="hr_resumes")
    notifications = relationship("EmailNotification", back_populates="resume")
