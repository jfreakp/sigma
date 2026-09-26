from fastapi import APIRouter

from app.api.v1.endpoints import auth, diagnostico, ordenes, revision_vehicular, tramites_anuales, tramites_vehiculares

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(revision_vehicular.router, tags=["revision-vehicular"])
api_router.include_router(tramites_vehiculares.router, tags=["tramites-vehiculares"])
api_router.include_router(tramites_anuales.router, tags=["tramites-anuales"])
api_router.include_router(ordenes.router, tags=["ordenes"])
api_router.include_router(diagnostico.router, tags=["diagnostico"])
