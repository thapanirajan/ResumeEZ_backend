import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from src.config.base import Base


class CandidateResume(Base):
    __tablename__ = "candidate_resumes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    title = Column(String)
    file_path = Column(String)
    resume_text = Column(Text)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    candidate = relationship("Candidate", back_populates="resumes")
    comparisons = relationship("ResumeComparison", back_populates="resume")
    roadmaps = relationship("LearningRoadmap", back_populates="resume")
