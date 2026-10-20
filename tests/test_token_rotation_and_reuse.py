"""Tests for Refresh Token Rotation and Token Family Reuse Detection."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import RefreshToken
from app.models.user import User


@pytest.mark.asyncio
async def test_refresh_token_rotation_success(client: AsyncClient, regular_user: User):
    """Test standard token rotation issuing a new token and revoking the old one."""
    # 1. Login to obtain initial token pair (Token A)
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user.email, "password": "UserPass123!"},
    )
    assert login_res.status_code == 200
    token_a = login_res.json()["refresh_token"]

    # 2. Rotate Token A -> yields Token B
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_a},
    )
    assert refresh_res.status_code == 200
    token_b = refresh_res.json()["refresh_token"]

    assert token_b != token_a
    assert "access_token" in refresh_res.json()

    # 3. Rotate Token B -> yields Token C
    refresh_res_2 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_b},
    )
    assert refresh_res_2.status_code == 200
    token_c = refresh_res_2.json()["refresh_token"]
    assert token_c != token_b


@pytest.mark.asyncio
async def test_refresh_token_reuse_detection_revokes_entire_family(
    client: AsyncClient, regular_user: User, db_session: AsyncSession
):
    """
    CRITICAL SECURITY TEST:
    When an already-rotated refresh token is reused (indicating token theft),
    the system must detect reuse, immediately revoke the entire token family,
    and reject subsequent requests from both legitimate and stolen tokens.
    """
    # 1. User logs in, receives Token 1
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": regular_user.email, "password": "UserPass123!"},
    )
    assert login_res.status_code == 200
    token_1 = login_res.json()["refresh_token"]

    # 2. Legitimate user rotates Token 1 -> receives Token 2
    rotate_res_1 = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert rotate_res_1.status_code == 200
    token_2 = rotate_res_1.json()["refresh_token"]

    # 3. Attacker (or compromised client) attempts to reuse the already-rotated Token 1!
    reuse_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_1},
    )
    assert reuse_res.status_code == 401
    assert "reuse detected" in reuse_res.json()["detail"].lower()

    # 4. Now verify that Token 2 (the legitimate client's token) is ALSO revoked because the family was revoked!
    legit_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_2},
    )
    assert legit_res.status_code == 401
    assert "reuse detected" in legit_res.json()["detail"].lower()

    # 5. Check database state: all tokens in the family should have is_revoked == True
    stmt = select(RefreshToken).where(RefreshToken.user_id == regular_user.id)
    tokens_in_db = (await db_session.execute(stmt)).scalars().all()
    assert len(tokens_in_db) >= 2
    for t in tokens_in_db:
        assert t.is_revoked is True


@pytest.mark.asyncio
async def test_refresh_token_invalid_token_string(client: AsyncClient):
    """Test rejection when submitting an unknown refresh token."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "completely-fake-refresh-token-string-value"},
    )
    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"]
