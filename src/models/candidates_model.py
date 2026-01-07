import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.config.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    full_name = Column(String)
    phone = Column(String)
    current_position = Column(String)
    experience_years = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="candidate")
    resumes = relationship("CandidateResume", back_populates="candidate")
    comparisons = relationship("ResumeComparison", back_populates="candidate")
    roadmaps = relationship("LearningRoadmap", back_populates="candidate")
