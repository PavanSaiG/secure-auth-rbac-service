"""Tests for token revocation, logout, and blacklist enforcement."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import User


@pytest.mark.asyncio
async def test_logout_blacklists_access_token(client: AsyncClient, regular_user: User):
    """Test that logging out blacklists the access token JTI, preventing subsequent calls."""
    # 1. Login to obtain access token
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user.email, "password": "UserPass123!"},
    )
    assert login_res.status_code == 200
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Access /me prior to logout -> 200 OK
    me_before = await client.get("/api/v1/auth/me", headers=headers)
    assert me_before.status_code == 200

    # 3. Call logout
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200

    # 4. Attempt to reuse the same access token -> 401 Revoked
    me_after = await client.get("/api/v1/auth/me", headers=headers)
    assert me_after.status_code == 401
    assert "Token has been revoked" in me_after.json()["detail"]


@pytest.mark.asyncio
async def test_expired_access_token_rejected(client: AsyncClient, regular_user: User):
    """Test that expired JWT access tokens are rejected with 401."""
    # Generate token already expired 5 minutes ago
    expired_token, _, _ = create_access_token(
        user_id=regular_user.id,
        email=regular_user.email,
        role=regular_user.role,
        expires_delta=timedelta(minutes=-5),
    )

    headers = {"Authorization": f"Bearer {expired_token}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
