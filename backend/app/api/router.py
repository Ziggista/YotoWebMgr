from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.library import router as library_router
from app.api.routes.settings import router as settings_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(imports_router, prefix="/imports", tags=["imports"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(library_router, prefix="/library", tags=["library"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
