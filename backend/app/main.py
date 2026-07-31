from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from slowapi.errors import RateLimitExceeded
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.api.routes.metrics import router as metrics_router_root
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import IdempotencyMiddleware, RequestContextMiddleware
from app.core.ratelimit import limiter

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


configure_logging()

if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Connect the background job queue (Redis + ARQ). If Redis is unreachable
    # the app keeps working and jobs fall back to running inline.
    from app.core import jobs
    from app.core.middleware import init_metrics

    init_metrics()
    try:
        pool = await jobs.create_redis_pool()
        jobs.set_redis_pool(pool)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Redis unavailable, background jobs disabled", exc_info=True
        )
    yield
    current_pool = jobs.get_redis_pool()
    if current_pool is not None:
        await current_pool.aclose()
        jobs.set_redis_pool(None)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestContextMiddleware)


async def _rate_limit_exceeded_handler(
    _request: Request, _exc: Exception
) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down."},
    )


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(metrics_router_root)
app.frontend("/", directory=FRONTEND_DIR)
