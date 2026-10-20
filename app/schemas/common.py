"""Common reusable Pydantic schemas."""

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated envelope."""

    items: list[T]
    total: int = Field(ge=0, description="Total matching items")
    limit: int = Field(ge=1, description="Page limit applied")
    offset: int = Field(ge=0, description="Page offset applied")


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = "healthy"
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    components: dict[str, str] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standardized error structure with correlation ID."""

    detail: str
    code: str
    correlation_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(extra="ignore")
