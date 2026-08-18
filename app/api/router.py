from fastapi import APIRouter

from app.api.routes import auth, diagnoses, health, integrations, routines

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(integrations.router, prefix="/integrations", tags=["integrations"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(diagnoses.router, prefix="/diagnoses", tags=["diagnoses"])
api_router.include_router(routines.router, prefix="/routines", tags=["routines"])
