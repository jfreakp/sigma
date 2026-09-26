from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router

app = FastAPI(title="Revisión Vehicular API")

# Fallos al conectar con la base de GIM (red caída, servidor apagado, timeout).
# OSError incluye ConnectionRefusedError, TimeoutError y errores de DNS.
GIM_CONNECTION_ERRORS = (OSError, OperationalError, InterfaceError)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": getattr(exc, "error_code", "HTTP_ERROR"),
            **getattr(exc, "extra", {}),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error_code": "VALIDATION_ERROR"},
    )


async def gim_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "No hay conexión con la base de datos de GIM", "error_code": "GIM_NO_DISPONIBLE"},
    )


for _error_class in GIM_CONNECTION_ERRORS:
    app.add_exception_handler(_error_class, gim_unavailable_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(api_router, prefix="/api/v1")
