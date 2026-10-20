"""Token rotation, token family tracking, reuse detection, and revocation service."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_secure_token_string,
    hash_token,
)
from app.models.revoked_token import RevokedToken
from app.models.token import RefreshToken
from app.models.user import User
from app.schemas.token import TokenResponse

logger = logging.getLogger(__name__)


async def issue_token_pair(
    db: AsyncSession,
    user: User,
    family_id: str | None = None,
) -> TokenResponse:
    """
    Issue a new access token and refresh token pair.
    Creates a new token family if family_id is None.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    family_id = family_id or str(uuid.uuid4())

    # 1. Create short-lived Access Token
    access_token, _, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    # 2. Generate cryptographically random refresh token
    raw_refresh_token = generate_secure_token_string()
    token_digest = hash_token(raw_refresh_token)
    refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # 3. Persist Refresh Token record in database
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=token_digest,
        family_id=family_id,
        is_revoked=False,
        expires_at=refresh_expires_at,
    )
    db.add(db_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
    )


async def rotate_refresh_token(
    db: AsyncSession,
    raw_refresh_token: str,
) -> TokenResponse:
    """
    Rotate a refresh token with Automatic Token Reuse Detection.

    If an already-revoked or already-used token from a family is presented again,
    the entire token family is immediately revoked, protecting against token theft.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    incoming_hash = hash_token(raw_refresh_token)

    # 1. Look up token by hash
    stmt = select(RefreshToken).where(RefreshToken.token_hash == incoming_hash)
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        logger.warning("Refresh token rotation rejected: token not found")
        raise ValueError("Invalid refresh token")

    # 2. Token Reuse Detection
    if token_record.is_revoked:
        # Breached token detected! An already rotated/revoked token was reused.
        # Revoke the ENTIRE token family immediately.
        logger.critical(
            f"REFRESH TOKEN REUSE DETECTED! Family: {token_record.family_id}, "
            f"User: {token_record.user_id}. Revoking entire family."
        )
        revoke_family_stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == token_record.family_id)
            .values(is_revoked=True)
        )
        await db.execute(revoke_family_stmt)
        await db.commit()

        raise PermissionError(
            "Security alert: Refresh token reuse detected. All sessions in this family have been revoked."
        )

    # 3. Check token expiration
    expires_at = token_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now:
        token_record.is_revoked = True
        await db.commit()
        logger.warning(f"Refresh token {token_record.id} expired at {token_record.expires_at}")
        raise ValueError("Refresh token has expired")

    # 4. Fetch associated user
    stmt_user = select(User).where(User.id == token_record.user_id)
    user_res = await db.execute(stmt_user)
    user = user_res.scalar_one_or_none()

    if not user or not user.is_active:
        token_record.is_revoked = True
        await db.commit()
        raise ValueError("User account is inactive or not found")

    # 5. Rotate: Invalidate current token and link replacement
    new_raw_token = generate_secure_token_string()
    new_token_hash = hash_token(new_raw_token)

    token_record.is_revoked = True
    token_record.replaced_by = new_token_hash

    # 6. Issue new token within SAME family
    new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    new_db_token = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        family_id=token_record.family_id,
        is_revoked=False,
        expires_at=new_expires_at,
    )
    db.add(new_db_token)

    # 7. Issue new Access Token
    access_token, _, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
    )

    await db.commit()
    logger.info(f"Rotated refresh token for user {user.id} in family {token_record.family_id}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw_token,
        token_type="bearer",
        expires_in=expires_in,
    )


async def revoke_refresh_token(
    db: AsyncSession,
    raw_refresh_token: str,
    revoke_entire_family: bool = False,
) -> bool:
    """Revoke a refresh token or its entire family on logout."""
    token_digest = hash_token(raw_refresh_token)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_digest)
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        return False

    if revoke_entire_family:
        revoke_stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == token_record.family_id)
            .values(is_revoked=True)
        )
        await db.execute(revoke_stmt)
    else:
        token_record.is_revoked = True

    await db.commit()
    return True


async def revoke_all_user_tokens(db: AsyncSession, user_id: str) -> int:
    """Revoke all active refresh tokens for a user across all sessions/devices."""
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)  # noqa: E712
        .values(is_revoked=True)
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount or 0


async def blacklist_access_token(
    db: AsyncSession,
    jti: str,
    user_id: str,
    exp_timestamp: int,
) -> None:
    """Add access token JTI to server-side revocation denylist."""
    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=UTC)
    revoked = RevokedToken(
        jti=jti,
        user_id=user_id,
        expires_at=exp_datetime,
    )
    db.add(revoked)
    await db.commit()


async def is_access_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    """Check if an access token JTI has been revoked prior to expiration."""
    stmt = select(RevokedToken).where(RevokedToken.jti == jti)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
