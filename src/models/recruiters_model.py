import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.config.base import Base


class Recruiter(Base):
    __tablename__ = "recruiters"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    company_name = Column(String)
    company_industry = Column(String)
    company_location = Column(String)
    company_website = Column(String)
    # job_title = Column(String)
    # job_description = Column(String)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="recruiter")
    jobs = relationship("Job", back_populates="recruiter")
