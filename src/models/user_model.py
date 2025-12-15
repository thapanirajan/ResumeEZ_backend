import uuid

from sqlalchemy import Column, String, Boolean, Enum
import enum

from src.config.base import Base


class UserRoles(enum.Enum):
    HR = "HR"
    USER = "USER"


class User(Base):
    # Table name
    __tablename__ = "user"

    id = Column(String, primary_key=True,default=lambda: str(uuid.uuid4()))
    username = Column(String, nullable=True)
    email = Column(String)
    password = Column(String)
    is_verified = Column(Boolean, default=False)
    role = Column(Enum(UserRoles), default=UserRoles.USER, nullable=False)
