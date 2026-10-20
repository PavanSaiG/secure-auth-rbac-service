"""Cryptographic operations: Argon2id password hashing, JWT encoding/decoding, and token hashing."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings
from app.models.user import UserRole
from app.schemas.token import TokenPayload

# Argon2id password hasher configured with OWASP recommended parameters
# memory_cost=65536 (64 MiB), time_cost=3 iterations, parallelism=4 threads
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
)


def hash_password(plain_password: str) -> str:
    """Hash password using Argon2id algorithm."""
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of raw refresh token for safe database persistence."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_secure_token_string(length: int = 48) -> str:
    """Generate cryptographically secure random token string."""
    return secrets.token_urlsafe(length)


def create_access_token(
    user_id: str,
    email: str,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, int]:
    """
    Generate signed JWT access token.

    Returns:
        tuple[str, str, int]: (token_string, jti, expires_in_seconds)
    """
    settings = get_settings()
    now = datetime.now(UTC)
    delta = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire_at = now + delta
    jti = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire_at.timestamp()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    return token, jti, int(delta.total_seconds())


def decode_and_verify_access_token(token: str) -> TokenPayload:
    """
    Decode and cryptographically verify JWT access token.
    Validates signature, expiration, issuer, audience, and permitted algorithm.
    """
    settings = get_settings()
    try:
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["sub", "email", "role", "jti", "exp", "iss", "aud"],
            },
        )
        return TokenPayload(**decoded)
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except jwt.InvalidIssuerError as exc:
        raise ValueError("Invalid token issuer") from exc
    except jwt.InvalidAudienceError as exc:
        raise ValueError("Invalid token audience") from exc
    except jwt.InvalidAlgorithmError as exc:
        raise ValueError("Invalid signing algorithm") from exc
    except jwt.PyJWTError as exc:
        raise ValueError(f"Token validation error: {exc}") from exc
