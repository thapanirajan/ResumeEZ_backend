from src.utils.error_code import ErrorCode, get_status_code_for_error_code

class AppException(Exception):
    def __init__(
            self,
            code: str | ErrorCode,
            message: str,
            status_code: int | None = None,
            details: dict | None = None,
    ):
        self.code = code
        self.message = message
        
        if status_code is None and isinstance(code, ErrorCode):
            self.status_code = get_status_code_for_error_code(code)
        else:
            self.status_code = status_code if status_code is not None else 400
            
        self.details = details
