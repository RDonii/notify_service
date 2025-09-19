from contextlib import asynccontextmanager
from fastapi import FastAPI
import redis.asyncio as redis

from app.core.config import settings
from app.api.v1.routes.publish import router as internal_publish_router
from app.api.v1.routes.stream import router as external_stream_router
from app.api.v1.routes.health import router as health_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield
    finally:
        await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

    prefix = settings.API_V1_PREFIX.rstrip("/")

    # Internal (no auth): publishers inside private network
    app.include_router(internal_publish_router, prefix=f"{prefix}/internal")

    # External (auth): public clients (SSE, later history)
    app.include_router(external_stream_router, prefix=f"{prefix}/external")

    # Health
    app.include_router(health_router, prefix=f"{prefix}/notify")

    return app
