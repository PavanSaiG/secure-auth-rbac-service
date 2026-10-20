"""Health check endpoints for container and load balancer probes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns healthy status if the service process is responding.",
)
async def liveness_probe() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
        components={"server": "up"},
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Validates active connectivity to database.",
)
async def readiness_probe(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    settings = get_settings()
    components: dict[str, str] = {}
    is_ready = True

    try:
        await db.execute(text("SELECT 1"))
        components["database"] = "healthy"
    except Exception as exc:
        components["database"] = f"unhealthy: {exc}"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_ready else "degraded",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(UTC),
        components=components,
    )
