"""Correlation ID ASGI middleware for request tracking."""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import set_correlation_id

CORRELATION_ID_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects or propagates correlation ID across request life cycle."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        corr_id = (
            request.headers.get(CORRELATION_ID_HEADER)
            or request.headers.get("x-request-id")
            or str(uuid.uuid4())
        )
        set_correlation_id(corr_id)
        request.state.correlation_id = corr_id

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = corr_id
        return response
