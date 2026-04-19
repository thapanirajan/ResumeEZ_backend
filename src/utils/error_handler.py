

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "Invalid request"
    if any(err.get("loc") == ("body", "email") or err.get("loc") == ["body", "email"] for err in errors):
        message = "Invalid email address"

    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": {
                "code": ErrorCode.VALIDATION_ERROR,
                "message": message,
                "details": {"errors": errors},
            },
        },
    )
