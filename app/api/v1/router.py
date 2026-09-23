from fastapi import APIRouter

from app.api.v1.endpoints import auth, catalogos

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(catalogos.router, tags=["catalogos"])
