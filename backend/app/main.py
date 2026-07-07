from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title="YotoWebMgr API",
    version="0.1.0",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"])
async def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}

