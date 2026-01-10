from datetime import timedelta, datetime

from fastapi import APIRouter, HTTPException, Response
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.user_schema import UpdateUserSchema, LoginResponse, LoginResponseData, PasswordlessLoginRequest, \
    PasswordlessLoginResponse, PasswordlessLoginVerify, SetUserRoleSchema, SetRoleResponse, SetRoleResponseData
from src.services.auth_services import get_user_by_email
from src.utils.email_service import send_verification_email
from src.utils.errors import UserErrors
from src.utils.exceptions import AppException
from src.utils.jwt_utils import create_jwt_token
from src.utils.utils import hash_otp, verify_otp, generate_email_verification_code
from fastapi import Response

user_router = APIRouter(tags=["User"])


@user_router.post("/auth/authenticate", response_model=PasswordlessLoginResponse)
async def authenticate(data: PasswordlessLoginRequest, db: AsyncSession = Depends(get_db)):
    print("--------- data from frontend---------")
    print(data)

    user = await get_user_by_email(db, data.email)
    otp = generate_email_verification_code()

    hashed_otp = hash_otp(otp)

    if not user:
        user = User(
            email=data.email,
            is_email_verified=False,
        )

        db.add(user)

    user.otp = hashed_otp
    user.otp_expires = datetime.now() + timedelta(minutes=5)
    await db.commit()

    await send_verification_email(user.email, otp)

    return PasswordlessLoginResponse(
        success=True,
        msg=" Please check you mail for otp "
    )


@user_router.post("/auth/verify", response_model=LoginResponse)
async def verify_login(data: PasswordlessLoginVerify, res: Response, db: AsyncSession = Depends(get_db)):
    try:
        print("----Data from frontend-----")
        print(data)
        user = await get_user_by_email(db, data.email)

        if not user:
            raise UserErrors.USER_NOT_FOUND

        # otp exists
        if not user.otp or not user.otp_expires:
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="Invalid otp"
            )

        # check otp expiry
        if user.otp_expires < datetime.now():
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="OTP expired"
            )

        # verify otp
        if not verify_otp(data.otp, user.otp):
            raise AppException(
                code="INVALID_OTP",
                status_code=400,
                message="Invalid otp"
            )

        # success
        user.otp = None
        user.otp_expires = None
        user.is_email_verified = True

        await db.commit()

        # create jwt tokens
        token = create_jwt_token(
            data={
                "sub": str(user.id),
                "email": user.email
            },
            expires_delta=timedelta(minutes=60)
        )

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
                id=user.id,
                email=user.email,
                role=user.role
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@user_router.get("/me")
async def get_logged_in_user(current_user=Depends(get_current_user)):
    return current_user


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

    return SetRoleResponse(
        success=True,
        message="Successfully set role",
        data=SetRoleResponseData(
            id=current_user.id,
            email=current_user.email,
            role=current_user.role
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


@user_router.patch("/{user_id}")
async def update_profile(payload: UpdateUserSchema, db: AsyncSession = Depends(get_db), ):
    pass
