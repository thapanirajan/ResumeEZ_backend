import os
import urllib.parse
from datetime import timedelta, datetime, timezone

import requests
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from src.config.db import get_db
from src.config.env_config import ENV_CONFIG
from src.middlewares.auth_middleware import get_current_user
from src.models import User, CandidateProfile, RecruiterProfile
from src.models.user_model import UserRole
from src.schema.user_schema import LoginResponse, LoginResponseData, PasswordlessLoginRequest, \
    PasswordlessLoginResponse, PasswordlessLoginVerify, SetUserRoleSchema, SetRoleResponse, SetRoleResponseData, \
    UserProfileResponse, UserProfileResponseData, UserProfileUpdateSchema
from src.services.auth_services import get_user_by_email
from src.services.user_services import get_user_by_id_service
from src.utils.email_service import send_verification_email
from src.utils.error_code import ErrorCode
from src.utils.errors import UserErrors
from src.utils.exceptions import AppException
from src.utils.jwt_utils import create_jwt_token
from src.utils.utils import hash_otp, verify_otp, generate_email_verification_code
from fastapi import Response

user_router = APIRouter(tags=["User"])
ACCESS_TOKEN_EXPIRE_DAYS = max(1, ENV_CONFIG.ACCESS_TOKEN_EXPIRE_DAYS)
ACCESS_TOKEN_EXPIRE_DELTA = timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
ACCESS_TOKEN_MAX_AGE_SECONDS = int(ACCESS_TOKEN_EXPIRE_DELTA.total_seconds())


def issue_auth_cookie(response: Response, token: str) -> None:
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        secure=is_production,
        samesite="none" if is_production else "lax",
        max_age=ACCESS_TOKEN_MAX_AGE_SECONDS,
        path="/",
    )


@user_router.post("/auth/authenticate", response_model=PasswordlessLoginResponse)
async def authenticate(data: PasswordlessLoginRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_email(db, data.email)
    otp = generate_email_verification_code()

    hashed_otp = hash_otp(otp)

    if not user:
        user = User(
            email=data.email,
            is_verified=False,
        )

        db.add(user)

    user.otp_code = hashed_otp
    user.expires_at = datetime.now() + timedelta(minutes=5)
    await db.commit()

    await send_verification_email(str(user.email), otp)

    return PasswordlessLoginResponse(
        success=True,
        msg=" Please check you mail for otp "
    )


@user_router.post("/auth/verify", response_model=LoginResponse)
async def verify_login(data: PasswordlessLoginVerify, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        print("---------Payload from frontend-------")
        print(data)
        user = await get_user_by_email(db, data.email)

        if not user:
            raise AppException(
                ErrorCode.USER_NOT_FOUND,
                "User not found"
            )

        # otp exists
        if not user.otp_code or not user.expires_at:
            raise AppException(
                ErrorCode.OTP_EXPIRED,
                "OTP Expired"
            )

        # check otp expiry
        if user.expires_at < datetime.now(timezone.utc):
            raise AppException(
                ErrorCode.OTP_EXPIRED,
                "OTP Expired"
            )

        # verify otp
        if not verify_otp(data.otp_code, user.otp_code):
            raise AppException(
                ErrorCode.OTP_EXPIRED,
                "OTP Expired"
            )

        # success
        user.otp_code = None
        user.expires_at = None
        user.is_verified = True

        await db.commit()

        # create jwt tokens
        token = create_jwt_token(
            data={
                "sub": str(user.id),
                "email": user.email
            },
            expires_delta=ACCESS_TOKEN_EXPIRE_DELTA
        )
        print("-----Token----------")
        print(token)

        issue_auth_cookie(response, token)

        return LoginResponse(
            success=True,
            message="Successfully logged in",
            data=LoginResponseData(
                id=str(user.id),
                email=user.email
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@user_router.get("/auth/google/login")
async def google_login():
    params = {
        "client_id": ENV_CONFIG.GOOGLE_CLIENT_ID,
        "redirect_uri": ENV_CONFIG.GOOGLE_CLIENT_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@user_router.get("/auth/google/callback")
async def google_oauth_callback(code: str, db: AsyncSession = Depends(get_db)):
    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": ENV_CONFIG.GOOGLE_CLIENT_ID,
            "client_secret": ENV_CONFIG.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": ENV_CONFIG.GOOGLE_CLIENT_REDIRECT_URI,
        },
    ).json()

    info = id_token.verify_oauth2_token(
        token_res["id_token"],
        google_requests.Request(),
        ENV_CONFIG.GOOGLE_CLIENT_ID,
    )

    email = info["email"]

    user = await db.execute(
        select(User).where(User.email == email)
    )

    user = user.scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            is_verified=True,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_jwt_token(
        data={
            "sub": str(user.id),
            "email": user.email
        },
        expires_delta=ACCESS_TOKEN_EXPIRE_DELTA
    )

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redirect = RedirectResponse(f"{frontend_url}/auth/callback")
    issue_auth_cookie(redirect, token)
    return redirect


@user_router.get("/me")
async def get_logged_in_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user.id
    user_profile = await get_user_by_id_service(db, user_id)
    return user_profile


@user_router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await get_user_by_id_service(db, current_user.id)

    if user is None:
        raise AppException(
            ErrorCode.USER_NOT_FOUND,
            "User not found",
        )

    if user.role == UserRole.JOB_SEEKER and user.candidate_profile is None:
        candidate = CandidateProfile(user_id=user.id)
        db.add(candidate)
        await db.commit()
        user = await get_user_by_id_service(db, current_user.id)
    elif user.role == UserRole.RECRUITER and user.recruiter_profile is None:
        recruiter = RecruiterProfile(user_id=user.id)
        db.add(recruiter)
        await db.commit()
        user = await get_user_by_id_service(db, current_user.id)

    return UserProfileResponse(
        success=True,
        message="Profile fetched successfully",
        data=UserProfileResponseData.model_validate(user),
    )


@user_router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
        payload: UserProfileUpdateSchema,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id_service(db, current_user.id)

    if user is None:
        raise AppException(
            ErrorCode.USER_NOT_FOUND,
            "User not found",
        )

    if user.role is None:
        raise AppException(
            ErrorCode.INVALID_INPUT,
            "Role is not set for this user",
        )

    update_data = payload.model_dump(exclude_unset=True)

    if user.role == UserRole.JOB_SEEKER:
        if user.candidate_profile is None:
            user.candidate_profile = CandidateProfile(user_id=user.id)

        allowed_fields = {"username", "full_name", "current_role", "experience_years"}
        for field, value in update_data.items():
            if field in allowed_fields:
                setattr(user.candidate_profile, field, value)
    elif user.role == UserRole.RECRUITER:
        if user.recruiter_profile is None:
            user.recruiter_profile = RecruiterProfile(user_id=user.id)

        allowed_fields = {"username", "full_name"}
        for field, value in update_data.items():
            if field in allowed_fields:
                setattr(user.recruiter_profile, field, value)

    await db.commit()

    updated_user = await get_user_by_id_service(db, current_user.id)
    return UserProfileResponse(
        success=True,
        message="Profile updated successfully",
        data=UserProfileResponseData.model_validate(updated_user),
    )


@user_router.patch("/auth/set-role", response_model=SetRoleResponse)
async def set_user_role(data: SetUserRoleSchema, current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    if current_user.role is not None:
        raise AppException(
            ErrorCode.ROLE_ALREADY_SET,
            "Role already set",
        )

    current_user.role = data.role
    await db.commit()
    await db.refresh(current_user)

    # initialize Recruiter and Candidate Table
    if data.role == UserRole.JOB_SEEKER:
        candidate = CandidateProfile(user_id=current_user.id)
        db.add(candidate)
    elif data.role == UserRole.RECRUITER:
        recruiter = RecruiterProfile(user_id=current_user.id)
        db.add(recruiter)

    await db.commit()

    return SetRoleResponse(
        success=True,
        message="Successfully set role",
        data=SetRoleResponseData(
            id=current_user.id,
            email=current_user.email
        )
    )


@user_router.post("/logout")
async def logout(res: Response):
    res.delete_cookie(
        key="token",
        path="/"
    )
    return {
        "success": True,
        "message": "Successfully logged out"
    }
