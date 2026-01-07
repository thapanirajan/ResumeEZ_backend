from datetime import timedelta, datetime
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import EmailVerification, User
from src.models.user_model import UserRole
from src.schema.user_schema import RegisterSchema, UpdateUserSchema, LoginResponse, LoginResponseData, \
    RegisterResponse, GetAllUserResponse, PasswordlessLoginRequest, PasswordlessLoginResponse, PasswordlessLoginVerify
from src.services.auth_services import register_user_service, get_user_by_email
from src.services.user_services import get_all_users_service
from src.utils.email_service import send_verification_email
from src.utils.errors import UserErrors, AuthError
from src.utils.exceptions import AppException
from src.utils.jwt_utils import create_jwt_token
from src.utils.utils import hash_otp, verify_otp, generate_email_verification_code

user_router = APIRouter(tags=["User"])


@user_router.post("/auth/register", response_model=RegisterResponse)
async def register(data: RegisterSchema, db: AsyncSession = Depends(get_db)):
    print("--------- data from frontend---------")
    print(data)
    # check if the user already exists
    user_exists = await get_user_by_email(db, data.email)

    if user_exists:
        raise UserErrors.USER_ALREADY_EXISTS

    if data.password != data.confirm_password:
        raise UserErrors.PASSWORD_MISMATCH

    # exclude confirm password
    user_data = data.model_dump(exclude={"confirm_password"})

    # hash password
    user_data["password"] = hash_otp(user_data["password"])

    # is verified
    user_data["is_email_verified"] = True

    token = generate_email_verification_code()

    # register user
    user = await register_user_service(db, user_data)

    verification = EmailVerification(
        user_id=user.id,
        verification_token=token,
        expires_at=datetime.now() + timedelta(minutes=5)
    )

    db.add(verification)
    await db.commit()

    # email token send logic
    await send_verification_email(data.email, token)

    return RegisterResponse(
        success=True,
        message="Successfully registered in. Please check you mail for email verification ",
    )


# @user_router.post("/login", response_model=LoginResponse)
# async def login_password(data: LoginSchema, db: AsyncSession = Depends(get_db)):
#     # find user
#     user = await get_user_by_email(db, data.email)
#     if not user:
#         raise UserErrors.USER_NOT_FOUND
#
#     # compare password
#     if not verify_password(data.password, user.password):
#         raise AuthError.INVALID_CREDENTIALS
#
#     if not user.is_email_verified:
#         token = generate_email_verification_code()
#         verification = EmailVerification(
#             user_id=user.id,
#             verification_token=token,
#             expires_at=datetime.now() + timedelta(minutes=5)
#         )
#
#         db.add(verification)
#         await db.commit()
#
#         await send_verification_email(user.email, token)
#
#         raise AppException(
#             code="USER_NOT_VERIFIED",
#             message="You account is not verified, we have send verification code to your email.",
#             status_code=400,
#         )
#
#     # create jwt token
#     token = create_jwt_token(
#         data={
#             "sub": str(user.id),
#             "email": user.email,
#             "role": user.role.value
#         },
#         expires_delta=timedelta(minutes=60)
#     )
#
#     return LoginResponse(
#         success=True,
#         message="Successfully logged in",
#         data=LoginResponseData(
#             id=user.id,
#             email=user.email,
#             username=user.email,
#             token=token,
#             role=user.role.value
#         )
#     )


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
async def verify_login(data: PasswordlessLoginVerify, db: AsyncSession = Depends(get_db)):
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
    if user.role is None:
        user.role = data.role

    await db.commit()

    # create jwt tokens
    token = create_jwt_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value
        },
        expires_delta=timedelta(minutes=60)
    )

    return LoginResponse(
        success=True,
        message="Successfully logged in",
        data=LoginResponseData(
            id=user.id,
            email=user.email,
            role=user.role.value if user.role else None,
            token=token
        )
    )


@user_router.get("/me")
async def get_profile(current_user=Depends(get_current_user)):
    return current_user


@user_router.get("", response_model=List[GetAllUserResponse])
async def get_all_users(db: AsyncSession = Depends(get_db)):
    users = await get_all_users_service(db)
    return users


@user_router.patch("/{user_id}")
async def update_profile(payload: UpdateUserSchema, db: AsyncSession = Depends(get_db), ):
    pass
