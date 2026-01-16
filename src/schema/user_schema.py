from datetime import datetime
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
    role: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    message: str
    data: LoginResponseData

