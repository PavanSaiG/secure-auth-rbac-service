"""Authentication and Role-Based Access Control FastAPI dependencies."""

from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_and_verify_access_token
from app.core.token_service import is_access_token_blacklisted
from app.database import get_db_session
from app.models.user import User, UserRole
from app.schemas.token import TokenPayload

security_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding active async database session."""
    async for session in get_db_session():
        yield session


def get_token_from_header_or_cookie(
    auth_header: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
) -> str:
    """Extract JWT token from Authorization Bearer header or HttpOnly cookie."""
    if auth_header and auth_header.credentials:
        return auth_header.credentials
    if access_token_cookie:
        return access_token_cookie

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_token_payload(
    raw_token: str = Depends(get_token_from_header_or_cookie),
    db: AsyncSession = Depends(get_db),
) -> tuple[TokenPayload, str]:
    """
    Cryptographically verify access token, validate expiration and claims,
    and verify the token JTI has not been blacklisted on logout.
    """
    try:
        payload = decode_and_verify_access_token(raw_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # Check server-side blacklist for immediate revocation enforcement
    if await is_access_token_blacklisted(db, payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload, raw_token


async def get_current_user(
    token_data: tuple[TokenPayload, str] = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Retrieve the active User entity corresponding to the verified token subject."""
    payload, _ = token_data
    stmt = select(User).where(User.id == payload.sub)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_role(*allowed_roles: UserRole) -> Callable[..., Any]:
    """
    Dependency factory enforcing Role-Based Access Control (RBAC).

    Usage:
        @router.get("/admin/resource", dependencies=[Depends(require_role(UserRole.ADMIN))])
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {role_names}",
            )
        return current_user

    return role_checker


def get_request_correlation_id(
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
) -> str | None:
    return x_correlation_id
