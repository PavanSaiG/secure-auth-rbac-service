"""FastAPI application factory, lifespan management, and AWS Lambda Mangum adapter."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from app.api import api_v1_router, health_router
from app.core.config import get_settings
from app.database import close_db, init_db
from app.logging_config import get_correlation_id, setup_logging
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.rate_limiter import SlidingWindowRateLimiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and graceful shutdown."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)
    logger.info(f"Starting {settings.APP_NAME} in '{settings.ENVIRONMENT}' environment")

    if "sqlite" in settings.DATABASE_URL:
        logger.info("Initializing SQLite tables...")
        await init_db()

    yield

    logger.info("Disposing database connection pools...")
    await close_db()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    settings = get_settings()

    app = FastAPI(
        title="Secure Authentication & Role Management Service",
        description=(
            "Production-grade Authentication and RBAC Service featuring Argon2id password hashing, "
            "Refresh Token Rotation with Token Family Reuse Detection, and strict role permissions."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. Security & Traceability Middleware
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(SlidingWindowRateLimiter)

    # 2. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 3. Exception Handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = get_correlation_id()
        errors = exc.errors()
        error_msg = "; ".join(f"{e.get('loc')}: {e.get('msg')}" for e in errors)
        logger.warning(f"Request validation failure: {error_msg}")

        error_response = ErrorResponse(
            detail=error_msg,
            code="VALIDATION_ERROR",
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = get_correlation_id()
        logger.exception(f"Unhandled server error: {exc}")

        error_response = ErrorResponse(
            detail="An unexpected internal error occurred.",
            code="INTERNAL_SERVER_ERROR",
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(mode="json"),
        )

    # 4. Mount Routes
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


app = create_app()

# AWS Lambda ASGI Adapter
handler = Mangum(app, lifespan="off")


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
