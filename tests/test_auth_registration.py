"""Tests for user registration, input validation, and password hashing."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user_success(client: AsyncClient):
    """Test successful user registration issuing access and refresh tokens."""
    payload = {
        "email": "new.user@example.com",
        "password": "SecurePassword123!",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert "X-Correlation-ID" in response.headers


@pytest.mark.asyncio
async def test_register_duplicate_email_conflict(client: AsyncClient):
    """Test rejection when registering with an existing email address."""
    payload = {
        "email": "duplicate.test@example.com",
        "password": "ValidPassword99#",
    }

    # First registration -> 201
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with identical email -> 409 Conflict
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_register_password_complexity_rules(client: AsyncClient):
    """Test password policy enforcement."""
    # 1. Too short
    res_short = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@test.com", "password": "Pass1!"},
    )
    assert res_short.status_code == 422

    # 2. Missing uppercase
    res_no_upper = await client.post(
        "/api/v1/auth/register",
        json={"email": "noupper@test.com", "password": "password123!"},
    )
    assert res_no_upper.status_code == 422

    # 3. Missing digit
    res_no_digit = await client.post(
        "/api/v1/auth/register",
        json={"email": "nodigit@test.com", "password": "Password!"},
    )
    assert res_no_digit.status_code == 422

    # 4. Missing special character
    res_no_symbol = await client.post(
        "/api/v1/auth/register",
        json={"email": "nosymbol@test.com", "password": "Password123"},
    )
    assert res_no_symbol.status_code == 422


@pytest.mark.asyncio
async def test_register_prevents_privilege_escalation(client: AsyncClient):
    """Verify that registering users are strictly granted USER role, ignoring extra fields."""
    payload = {
        "email": "hacker@example.com",
        "password": "Password123!",
        "role": "ADMIN",  # Attempt to self-assign ADMIN
    }

    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    tokens = res.json()

    # Query /me to verify assigned role
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me_res = await client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["role"] == "USER"  # Must be USER
