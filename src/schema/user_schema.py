from typing import Optional

from pydantic import BaseModel, EmailStr

from src.models.user_model import UserRoles


class User(BaseModel):
    id: str
    username: str
    email: str
    password: str
    is_verified: bool
    role: UserRoles
    google_id: str


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    role: UserRoles
    is_verified: Optional[bool] = True


class UpdateUserSchema(BaseModel):
    username: Optional[str] = None


class LoginSchema(BaseModel):
    email: EmailStr
    password: str
