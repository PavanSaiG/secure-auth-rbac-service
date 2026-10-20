"""Tests for user login, credential verification, and account status checks."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, regular_user: User):
    """Test successful login with valid credentials."""
    payload = {
        "email": regular_user.email,
        "password": "UserPass123!",
    }

    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, regular_user: User):
    """Test rejection on incorrect password."""
    payload = {
        "email": regular_user.email,
        "password": "WrongPassword999!",
    }

    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test rejection when user email is not registered."""
    payload = {
        "email": "ghost.user@example.com",
        "password": "AnyPassword123!",
    }

    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_deactivated_account_forbidden(client: AsyncClient, db_session: AsyncSession):
    """Test that deactivated accounts cannot log in."""
    deactivated = User(
        email="inactive.user@example.com",
        password_hash=hash_password("InactivePass123!"),
        role=UserRole.USER,
        is_active=False,
    )
    db_session.add(deactivated)
    await db_session.commit()

    payload = {
        "email": "inactive.user@example.com",
        "password": "InactivePass123!",
    }

    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"]
