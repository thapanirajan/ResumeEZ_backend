from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from src.models.user_model import UserRole


class UpdateUserSchema(BaseModel):
    username: Optional[str] = None



# login
class PasswordlessLoginRequest(BaseModel):
    email: str = Field(
        min_length=1,
        max_length=50,
        examples=["thapanirajan789@gmail.com"]
    )

# login response
class PasswordlessLoginResponse(BaseModel):
    success: bool
    msg: str



# verify otp
class PasswordlessLoginVerify(BaseModel):
    email: str
    otp_code: str


# set role
class SetUserRoleSchema(BaseModel):
    role: UserRole

# set role response
class SetRoleResponseData(BaseModel):
    id: UUID
    email: str

class SetRoleResponse(BaseModel):
    success: bool
    message: str
    data: SetRoleResponseData



class LoginResponseData(BaseModel):
    id: str
    email: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    data: LoginResponseData


class CandidateProfileSchema(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RecruiterProfileSchema(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponseData(BaseModel):
    id: UUID
    email: str
    role: Optional[UserRole] = None
    candidate_profile: Optional[CandidateProfileSchema] = None
    recruiter_profile: Optional[RecruiterProfileSchema] = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(BaseModel):
    success: bool
    message: str
    data: UserProfileResponseData


class UserProfileUpdateSchema(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[int] = None

