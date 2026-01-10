from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.models.user_model import UserRole


class User(BaseModel):
    id: str
    username: str
    email: str
    password: str
    is_email_verified: bool
    role: UserRole
    google_id: str


class RegisterSchema(BaseModel):
    email: str
    password: str
    confirm_password: str
    role: UserRole
    is_email_verified: Optional[bool] = True


class RegisterResponse(BaseModel):
    success: bool
    message: str


class UpdateUserSchema(BaseModel):
    username: Optional[str] = None


class PasswordlessLoginRequest(BaseModel):
    email: str = Field(
        min_length=1,
        max_length=50,
        examples=["thapanirajan789@gmail.com"]
    )



class PasswordlessLoginResponse(BaseModel):
    success: bool
    msg: str


class PasswordlessLoginVerify(BaseModel):
    email: str
    otp: str


class SetUserRoleSchema(BaseModel):
    role: UserRole

class SetRoleResponseData(BaseModel):
    id: UUID
    email: str
    role: UserRole

class SetRoleResponse(BaseModel):
    success: bool
    message: str
    data: SetRoleResponseData



class LoginResponseData(BaseModel):
    id: str
    email: str
    role: Optional[str] = None



class LoginResponse(BaseModel):
    success: bool
    message: str
    data: LoginResponseData


class UpdateRoleSchema(BaseModel):
    role: UserRole


class GetAllUserResponse(BaseModel):
    id: str
    username: Optional[str] = None
    email: str
    is_email_verified: bool
    created_at: datetime
    role: UserRole


class RegisterUserSchema(BaseModel):
    name: str  # this is required
    gender: Optional[str] = None  # this is optional this mean gender can be str oir optional
    # i cannot write gender: Optional[str] = None it must be string gender: Optional[str] = "admin"


# Learning Field in pydantic
# without fields
class FieldSchema(BaseModel):
    name: str
    age: int


# with Field - metadata for each variable
class FieldSchema2(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=20,
        description="Name description",  # for swagger
        examples=["Nirajan Thapa"]  # for swagger
    )
    age: int = Field(gt=5, lt=100),
    # nested schema
    field1: FieldSchema


# Response Schema
class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    model_config = ConfigDict(from_attributes=True)  # this sets ORM mode true

#
# FastAPI & Pydantic Schemas – Quick Recap
#
# Schemas = Pydantic models → define request/response data, auto-validate, auto-document.
#
# Optional fields → Optional[str] = None makes a field optional; str = "default" gives a default.
#
# Field validations → Field(min_length=3, max_length=50, gt=0, lt=120) adds rules + docs.
#
# Schema inheritance → reuse fields for Create/Update/Response; updates require optional fields.
#
# Update schemas → all fields optional, similar to Node.js partial() pattern.
#
# ORM Mode → allows Pydantic to read SQLAlchemy objects directly; keeps responses clean and safe.
#
# Best practice CRUD schemas:
#
# Base → shared fields
#
# Create → required fields
#
# Update → optional fields
#
# Response → include ID + orm_mode=True
