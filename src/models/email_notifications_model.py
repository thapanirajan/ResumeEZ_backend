import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.config.base import Base


class EmailNotification(Base):
    __tablename__ = "email_notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_email = Column(String, nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"))
    resume_id = Column(String, ForeignKey("hr_uploaded_resumes.id"))
    notification_type = Column(String)
    status = Column(String)
    sent_at = Column(DateTime)

    resume = relationship("HRUploadedResume", back_populates="notifications")
