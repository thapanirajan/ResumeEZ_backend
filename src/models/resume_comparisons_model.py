import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from src.config.base import Base


class ResumeComparison(Base):
    __tablename__ = "resume_comparisons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    resume_id = Column(String, ForeignKey("candidate_resumes.id"), nullable=False)
    job_description = Column(Text, nullable=False)
    missing_skills = Column(Text)
    match_score = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

    candidate = relationship("Candidate", back_populates="comparisons")
    resume = relationship("CandidateResume", back_populates="comparisons")
