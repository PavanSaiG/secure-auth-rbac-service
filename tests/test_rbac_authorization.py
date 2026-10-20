"""Tests for Role-Based Access Control (RBAC) and authorization boundaries."""

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_rbac_unauthenticated_request_rejected(client: AsyncClient):
    """Test that protected endpoints reject requests lacking credentials with 401."""
    res_me = await client.get("/api/v1/auth/me")
    assert res_me.status_code == 401

    res_admin = await client.get("/api/v1/admin/users")
    assert res_admin.status_code == 401


@pytest.mark.asyncio
async def test_rbac_me_accessible_to_all_authenticated_roles(
    client: AsyncClient,
    user_token: str,
    support_token: str,
    admin_token: str,
):
    """Test that all authenticated roles can access /me."""
    for token, expected_role in [
        (user_token, "USER"),
        (support_token, "SUPPORT"),
        (admin_token, "ADMIN"),
    ]:
        headers = {"Authorization": f"Bearer {token}"}
        res = await client.get("/api/v1/auth/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["role"] == expected_role


@pytest.mark.asyncio
async def test_rbac_admin_users_list_permissions(
    client: AsyncClient,
    user_token: str,
    support_token: str,
    admin_token: str,
):
    """
    Test permissions on /admin/users:
    - USER: 403 Forbidden
    - SUPPORT: 200 OK
    - ADMIN: 200 OK
    """
    # 1. Regular USER -> 403
    res_user = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert res_user.status_code == 403
    assert "Insufficient permissions" in res_user.json()["detail"]

    # 2. SUPPORT user -> 200 OK
    res_support = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {support_token}"}
    )
    assert res_support.status_code == 200
    assert "items" in res_support.json()

    # 3. ADMIN user -> 200 OK
    res_admin = await client.get(
        "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert "items" in res_admin.json()


@pytest.mark.asyncio
async def test_rbac_role_assignment_restricted_to_admin_only(
    client: AsyncClient,
    user_token: str,
    support_token: str,
    admin_token: str,
    regular_user: User,
):
    """
    Test permissions on /admin/users/{user_id}/role:
    - USER: 403 Forbidden
    - SUPPORT: 403 Forbidden
    - ADMIN: 200 OK
    """
    url = f"/api/v1/admin/users/{regular_user.id}/role"
    payload = {"role": "SUPPORT"}

    # 1. USER attempts role update -> 403
    res_user = await client.patch(
        url, json=payload, headers={"Authorization": f"Bearer {user_token}"}
    )
    assert res_user.status_code == 403

    # 2. SUPPORT attempts role update -> 403
    res_support = await client.patch(
        url, json=payload, headers={"Authorization": f"Bearer {support_token}"}
    )
    assert res_support.status_code == 403

    # 3. ADMIN performs role update -> 200 OK
    res_admin = await client.patch(
        url, json=payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_admin.status_code == 200
    assert res_admin.json()["role"] == "SUPPORT"
