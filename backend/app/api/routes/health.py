from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.foundation import BuildInfoResponse


router = APIRouter()
settings = get_settings()


@router.get("")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/build", response_model=BuildInfoResponse)
async def build_info() -> BuildInfoResponse:
    return BuildInfoResponse(
        service="api",
        build_sha=settings.app_build_sha,
        environment=settings.environment,
    )
