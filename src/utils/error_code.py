from enum import Enum


class ErrorCode(str, Enum):
    # Validation errors (400)
    VALIDATION_ERROR = 'VALIDATION_ERROR'
    INVALID_INPUT = 'INVALID_INPUT'

    # Authentication errors (401)
    AUTHENTICATION_FAILED = 'AUTHENTICATION_FAILED'
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    INVALID_TOKEN = 'INVALID_TOKEN'
    TOKEN_EXPIRED = 'TOKEN_EXPIRED'
    SESSION_REVOKED = 'SESSION_REVOKED'
    OTP_EXPIRED = 'OTP_EXPIRED'
    INVALID_OTP = 'INVALID_OTP'

    # Authorization errors (403)
    UNAUTHORIZED_ACCESS = 'UNAUTHORIZED_ACCESS'
    FORBIDDEN = 'FORBIDDEN'
    INSUFFICIENT_PERMISSIONS = 'INSUFFICIENT_PERMISSIONS'

    # Resource errors (404)
    RESOURCE_NOT_FOUND = 'RESOURCE_NOT_FOUND'
    USER_NOT_FOUND = 'USER_NOT_FOUND'

    # Conflict errors (409)
    DUPLICATE_RESOURCE = 'DUPLICATE_RESOURCE'
    EMAIL_ALREADY_EXISTS = 'EMAIL_ALREADY_EXISTS'
    ROLE_ALREADY_SET = 'ROLE_ALREADY_SET'

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
    TOO_MANY_REQUESTS = 'TOO_MANY_REQUESTS'

    # Server errors (500)
    INTERNAL_SERVER_ERROR = 'INTERNAL_SERVER_ERROR'
    DATABASE_ERROR = 'DATABASE_ERROR'
    EXTERNAL_SERVICE_ERROR = 'EXTERNAL_SERVICE_ERROR'

    # File upload errors (400)
    FILE_TOO_LARGE = 'FILE_TOO_LARGE'
    INVALID_FILE_TYPE = 'INVALID_FILE_TYPE'
    UPLOAD_FAILED = 'UPLOAD_FAILED'


def get_status_code_for_error_code(code: ErrorCode) -> int:
    status_map = {
        # 400 Bad Request
        ErrorCode.VALIDATION_ERROR: 400,
        ErrorCode.INVALID_INPUT: 400,
        ErrorCode.FILE_TOO_LARGE: 400,
        ErrorCode.INVALID_FILE_TYPE: 400,
        ErrorCode.UPLOAD_FAILED: 400,

        # 401 Unauthorized
        ErrorCode.AUTHENTICATION_FAILED: 401,
        ErrorCode.INVALID_CREDENTIALS: 401,
        ErrorCode.INVALID_TOKEN: 401,
        ErrorCode.TOKEN_EXPIRED: 401,
        ErrorCode.SESSION_REVOKED: 401,
        ErrorCode.OTP_EXPIRED: 401,
        ErrorCode.INVALID_OTP: 401,

        # 403 Forbidden
        ErrorCode.UNAUTHORIZED_ACCESS: 403,
        ErrorCode.FORBIDDEN: 403,
        ErrorCode.INSUFFICIENT_PERMISSIONS: 403,

        # 404 Not Found
        ErrorCode.RESOURCE_NOT_FOUND: 404,
        ErrorCode.USER_NOT_FOUND: 404,

        # 409 Conflict
        ErrorCode.DUPLICATE_RESOURCE: 409,
        ErrorCode.EMAIL_ALREADY_EXISTS: 409,
        ErrorCode.ROLE_ALREADY_SET: 409,

        # 429 Too Many Requests
        ErrorCode.RATE_LIMIT_EXCEEDED: 429,
        ErrorCode.TOO_MANY_REQUESTS: 429,

        # 500 Internal Server Error
        ErrorCode.INTERNAL_SERVER_ERROR: 500,
        ErrorCode.DATABASE_ERROR: 500,
        ErrorCode.EXTERNAL_SERVICE_ERROR: 500,
    }

    return status_map.get(code, 500)
