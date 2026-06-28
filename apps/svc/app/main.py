"""smfo-svc FastAPI entry point.

Bootstrap order:
1. Load secrets from Secret Manager into env (if USE_SECRET_MANAGER=true).
2. Read settings from env (cached).
3. Configure structured logging.
4. Configure Sentry if DSN provided.
5. Mount routers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

# Secret loading must happen before Settings is read (Settings caches via lru_cache).
from app.core import secrets

secrets.load_secrets_into_env()

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.routers import health  # noqa: E402

settings = get_settings()
configure_logging(level="DEBUG" if settings.DEBUG else "INFO")
logger = get_logger(__name__)


def _configure_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION,
            integrations=[FastApiIntegration()],
            send_default_pii=False,
            traces_sample_rate=0.1,
        )
        logger.info("sentry_initialised")
    except ImportError:
        logger.warning("sentry_sdk_not_installed")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "smfo_svc_starting",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        port=settings.PORT,
        use_secret_manager=settings.USE_SECRET_MANAGER,
        vertex_location=settings.VERTEX_AI_LOCATION,
    )
    _configure_sentry()
    yield
    logger.info("smfo_svc_stopping")


app = FastAPI(
    title="SMFO Service",
    description="Stern Mazal Family Office — agent platform (smfo-svc)",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Keep API docs internal-only.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.include_router(health.router)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION}
