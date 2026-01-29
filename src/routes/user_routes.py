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
    PasswordlessLoginResponse, PasswordlessLoginVerify, SetUserRoleSchema, SetRoleResponse, SetRoleResponseData
from src.services.auth_services import get_user_by_email
from src.services.user_services import get_user_by_id_service
from src.utils.email_service import send_verification_email
from src.utils.errors import UserErrors
from src.utils.exceptions import AppException
from src.utils.jwt_utils import create_jwt_token
from src.utils.utils import hash_otp, verify_otp, generate_email_verification_code
from fastapi import Response

user_router = APIRouter(tags=["User"])


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
async def verify_login(data: PasswordlessLoginVerify, res: Response, db: AsyncSession = Depends(get_db)):
    try:
        print("---------Payload from frontend-------")
        print(data)
        user = await get_user_by_email(db, data.email)

        if not user:
            raise UserErrors.USER_NOT_FOUND

        # otp exists
        if not user.otp_code or not user.expires_at:
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="Invalid otp"
            )

        # check otp expiry
        if user.expires_at < datetime.now(timezone.utc):
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="OTP expired"
            )

        # verify otp
        if not verify_otp(data.otp_code, user.otp_code):
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="Invalid otp"
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
            expires_delta=timedelta(minutes=60)
        )
        print("-----Token----------")
        print(token)

        res.set_cookie(
            key="token",
            value=token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=60 * 60,
            path="/"
        )

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
async def google_oauth_callback(code: str, res: Response, db: AsyncSession = Depends(get_db)):
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
        expires_delta=timedelta(minutes=60)
    )

    # res.set_cookie(
    #     key="token",
    #     value=token,
    #     httponly=True,
    #     secure=False,
    #     samesite="lax",
    #     path="/",
    #     max_age=60 * 60,
    # )

    return RedirectResponse(f"http://localhost:3000/auth/callback?token={token}")


@user_router.get("/me")
async def get_logged_in_user(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user_id = current_user.id
    user_profile = await get_user_by_id_service(db, user_id)
    return user_profile


@user_router.patch("/auth/set-role", response_model=SetRoleResponse)
async def set_user_role(data: SetUserRoleSchema, current_user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    if current_user.role is not None:
        raise AppException(
            code="ROLE_ALREADY_EXISTS",
            status_code=400,
            message="User already has role"
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
