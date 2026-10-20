"""In-memory sliding window rate limiting middleware to prevent brute force and credential stuffing."""

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings


class SlidingWindowRateLimiter(BaseHTTPMiddleware):
    """
    Sliding window rate limiter tracking request timestamps per client IP and path category.
    Returns 429 Too Many Requests when limits are exceeded.
    """

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        # In-memory storage: key -> list of float timestamps
        self.request_history: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, inspecting X-Forwarded-For when behind reverse proxies."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_rate_limit(self, path: str) -> int:
        """Determine rate limit based on endpoint sensitivity."""
        settings = get_settings()
        if "/api/v1/auth/login" in path:
            return settings.RATE_LIMIT_LOGIN_PER_MINUTE
        if "/api/v1/auth/register" in path:
            return settings.RATE_LIMIT_REGISTER_PER_MINUTE
        return settings.RATE_LIMIT_DEFAULT_PER_MINUTE

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Bypass rate limits for health checks and API documentation
        if path in ["/health", "/health/ready", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        limit = self._get_rate_limit(path)
        window_seconds = 60.0
        now = time.time()

        bucket_key = f"{client_ip}:{path}"
        history = self.request_history[bucket_key]

        # Prune timestamps older than window
        cutoff = now - window_seconds
        valid_timestamps = [t for t in history if t > cutoff]
        self.request_history[bucket_key] = valid_timestamps

        if len(valid_timestamps) >= limit:
            retry_after = int(window_seconds - (now - valid_timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Too many requests.",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        self.request_history[bucket_key].append(now)
        return await call_next(request)
