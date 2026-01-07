import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.config.base import Base


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    verification_token = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="email_verifications")
