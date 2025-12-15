from src.utils.exceptions import AppException


class AuthError:
    INVALID_CREDENTIALS = AppException(
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
        status_code=401,
    )

    UNAUTHORIZED = AppException(
        code="UNAUTHORIZED",
        message="Authentication required",
        status_code=401,
    )


class UserErrors:
    USER_ALREADY_EXISTS = AppException(
        code="USER_ALREADY_EXISTS",
        message="User with this email already exists",
        status_code=409,
    )

    USER_NOT_FOUND = AppException(
        code="USER_NOT_FOUND",
        message="User not found",
        status_code=404,
    )
