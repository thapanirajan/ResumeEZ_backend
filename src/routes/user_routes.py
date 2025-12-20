from datetime import timedelta

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.schema.user_schema import RegisterSchema, UpdateUserSchema, LoginSchema
from src.services.auth_services import register_user_service, get_user_by_email
from src.utils.email_service import send_verification_email
from src.utils.errors import UserErrors, AuthError
from src.utils.utils import hash_password, verify_password, create_jwt_token, generate_email_verification_code

user_router = APIRouter(tags=["User"])


@user_router.post("/auth/register")
async def register(data: RegisterSchema, db: AsyncSession = Depends(get_db)):
    try:

        print("--------- data from frontend---------")
        print(data)
        # check if the user already exists
        user_exists = await get_user_by_email(db, data.email)

        if user_exists:
            raise UserErrors.USER_ALREADY_EXISTS

        # exclude confirm password
        user_data = data.model_dump(exclude={"confirm_password"})

        # hash password
        user_data["password"] = hash_password(user_data["password"])

        # is verified
        user_data["is_verified"] = True

        # token = generate_email_verification_code()

        # email token send logic
        # await send_verification_email(data.email, token)

        # register user
        user = await register_user_service(db, user_data)

        print(user)

        return {
            "success": True,
            "message": "User created successfully",
            "data": {
                "id": user.id,
                "email": user.email,
                "username": user.email,
            }
        }

    except ValueError as e:
        print(e)
        raise HTTPException(status_code=400, detail=str(e))


@user_router.post("/auth/login")
async def login(data: LoginSchema, db: AsyncSession = Depends(get_db)):
    try:

        # find user
        user = await get_user_by_email(db, data.email)
        if not user:
            raise UserErrors.USER_NOT_FOUND

        # compare password
        if not verify_password(data.password, user.password):
            raise AuthError.INVALID_CREDENTIALS

        # create jwt token
        token = create_jwt_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "role": user.role.value
            },
            expires_delta=timedelta(minutes=60)
        )

        return {
            "success": True,
            "data": {
                "token": token,
                "email": user.email,
                "username": user.email,
                "role": user.role
            },
            "message": "Logged in successfully"
        }
    except ValueError as e:
        print(e)
        raise HTTPException(status_code=500, detail=str("Internal server error"))


@user_router.get("/")
async def get_all_users():
    pass


@user_router.patch("/{user_id}")
async def update_profile(payload: UpdateUserSchema, db: AsyncSession = Depends(get_db), ):
    pass
