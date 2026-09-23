from fastapi import HTTPException


class AppHTTPException(HTTPException):
    """HTTPException carrying a stable machine-readable error_code."""

    def __init__(self, status_code: int, detail: str, error_code: str):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
