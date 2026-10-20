"""Tests for sliding window rate limiting middleware."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limiter_blocks_excessive_requests(client: AsyncClient):
    """Test that exceeding the rate limit triggers 429 Too Many Requests."""
    # RATE_LIMIT_LOGIN_PER_MINUTE is set to 10
    login_payload = {
        "email": "rate.limit.test@example.com",
        "password": "WrongPassword123!",
    }

    status_codes = []
    for _ in range(12):
        res = await client.post(
            "/api/v1/auth/login",
            json=login_payload,
            headers={"X-Forwarded-For": "203.0.113.195"},
        )
        status_codes.append(res.status_code)

    # First 10 requests should be 401 (invalid credentials)
    assert status_codes[:10] == [401] * 10
    # 11th and 12th requests should be blocked by rate limiter with 429
    assert status_codes[10] == 429
    assert status_codes[11] == 429
