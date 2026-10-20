"""Tests for health check endpoints and security headers."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_liveness_endpoint(client: AsyncClient):
    """Test GET /health returns 200 OK."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"]["server"] == "up"


@pytest.mark.asyncio
async def test_health_readiness_endpoint(client: AsyncClient):
    """Test GET /health/ready returns 200 OK and database component."""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["components"]["database"] == "healthy"


@pytest.mark.asyncio
async def test_security_headers_present_on_responses(client: AsyncClient):
    """Verify that OWASP recommended security headers are injected into HTTP responses."""
    response = await client.get("/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in headers
    assert "Content-Security-Policy" in headers
