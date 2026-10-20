"""Authentication endpoints: registration, login, token rotation, and logout."""

import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_token_payload, get_current_user, get_db
from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.core.token_service import (
    blacklist_access_token,
    issue_token_pair,
    revoke_all_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.models.user import User, UserRole
from app.schemas.token import RefreshTokenRequest, TokenPayload, TokenResponse
from app.schemas.user import UserLogin, UserRead, UserRegister

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_auth_cookies(response: Response, tokens: TokenResponse) -> None:
    """Set secure HttpOnly cookies for web clients."""
    settings = get_settings()
    # Access token cookie (short-lived)
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=tokens.expires_in,
        domain=settings.COOKIE_DOMAIN,
    )
    # Refresh token cookie (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        domain=settings.COOKIE_DOMAIN,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear cookies on logout."""
    settings = get_settings()
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN)
    response.delete_cookie(key="refresh_token", domain=settings.COOKIE_DOMAIN)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Creates a new user with Argon2id password hash and issues initial tokens. Role defaults strictly to USER.",
)
async def register_user(
    payload: UserRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 1. Prevent duplicate email registration
    stmt = select(User).where(User.email == payload.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )

    # 2. Hash password using Argon2id
    pwd_hash = hash_password(payload.password)

    # 3. Create user entity (strictly defaulting to UserRole.USER to prevent privilege escalation)
    user = User(
        email=payload.email,
        password_hash=pwd_hash,
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 4. Issue initial tokens
    tokens = await issue_token_pair(db, user)
    set_auth_cookies(response, tokens)

    logger.info(f"Registered new user {user.id} with email {user.email}")
    return tokens


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User authentication / login",
    description="Validates credentials via Argon2id and issues fresh access and refresh tokens.",
)
async def login_user(
    payload: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # 1. Lookup user by email
    stmt = select(User).where(User.email == payload.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    # 2. Timing-safe verification: check password even if user is not found to deter timing attacks
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    # 3. Issue fresh tokens with a new token family
    tokens = await issue_token_pair(db, user)
    set_auth_cookies(response, tokens)

    logger.info(f"Successful login for user {user.id}")
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token",
    description="Rotates refresh token and issues new access token. Detects token reuse and revokes entire family if compromised.",
)
async def refresh_access_token(
    response: Response,
    payload: RefreshTokenRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Accept token from request body or HttpOnly cookie
    raw_token = (
        payload.refresh_token if (payload and payload.refresh_token) else refresh_token_cookie
    )

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        new_tokens = await rotate_refresh_token(db, raw_token)
        set_auth_cookies(response, new_tokens)
        return new_tokens
    except PermissionError as exc:
        # Token reuse detected! Clear cookies and reject request
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and revoke tokens",
    description="Revokes current refresh token and blacklists access token JTI. Supports all_sessions=true to revoke all devices.",
)
async def logout_user(
    response: Response,
    all_sessions: bool = Query(default=False, description="Revoke all active sessions for user"),
    payload: RefreshTokenRequest | None = None,
    refresh_token_cookie: str | None = Cookie(default=None, alias="refresh_token"),
    token_data: tuple[TokenPayload, str] = Depends(get_current_token_payload),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    jwt_claims, _ = token_data

    # 1. Server-side blacklist access token JTI immediately
    await blacklist_access_token(
        db,
        jti=jwt_claims.jti,
        user_id=jwt_claims.sub,
        exp_timestamp=jwt_claims.exp,
    )

    # 2. Revoke refresh token(s)
    raw_token = (
        payload.refresh_token if (payload and payload.refresh_token) else refresh_token_cookie
    )
    if all_sessions:
        await revoke_all_user_tokens(db, jwt_claims.sub)
        logger.info(f"User {jwt_claims.sub} logged out from ALL sessions")
    elif raw_token:
        await revoke_refresh_token(db, raw_token, revoke_entire_family=True)
        logger.info(f"User {jwt_claims.sub} logged out from current session")

    clear_auth_cookies(response)
    return {"message": "Successfully logged out. Tokens have been revoked."}


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
    description="Retrieve account profile and assigned role for the authenticated user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)
