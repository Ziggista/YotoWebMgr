import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings


settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app.request")

app = FastAPI(
    title="YotoWebMgr API",
    version="0.1.0",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "capacitor://localhost",
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
        "http://ziggi-pc-1.tailaf3d4b.ts.net:5175",
        "https://ziggi-pc-1.tailaf3d4b.ts.net",
        "http://100.65.175.83:5175",
    ],
    allow_origin_regex=r"^(capacitor://localhost|https?://localhost(?::\d+)?|https?://127\.0\.0\.1(?::\d+)?|https?://ziggi-pc-1\.tailaf3d4b\.ts\.net(?::\d+)?|https?://100\.65\.175\.83(?::\d+)?)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "HTTP %s %s -> %s in %.1fms from %s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request.client.host if request.client else "unknown",
    )
    return response


@app.get("/health", tags=["health"])
async def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}
