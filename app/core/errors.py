from fastapi import HTTPException


class AppHTTPException(HTTPException):
    """HTTPException carrying a stable machine-readable error_code.

    `extra` holds additional fields merged into the JSON error body
    (e.g. id_titulo for ORDEN_YA_EMITIDA).
    """

    def __init__(self, status_code: int, detail: str, error_code: str, extra: dict | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.extra = extra or {}
