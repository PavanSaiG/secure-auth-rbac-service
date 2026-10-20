"""Pytest fixtures and test environment setup for Auth & RBAC service."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

TEST_DB_FILE = "test_auth.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_FILE}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-unit-testing-purposes-only-32-chars"

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.database import close_db, init_db
from app.main import create_app
from app.models.user import User, UserRole

get_settings.cache_clear()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Create test database schema once for the entire test session."""
    db_path = Path(TEST_DB_FILE)
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass
    await init_db()
    yield
    await close_db()
    if db_path.exists():
        try:
            db_path.unlink()
        except OSError:
            pass


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session per test."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture(autouse=True)
async def clean_tokens_between_tests(db_session: AsyncSession):
    """Clean token tables before each test to guarantee fresh token state."""
    from app.models.revoked_token import RevokedToken
    from app.models.token import RefreshToken

    await db_session.execute(delete(RefreshToken))
    await db_session.execute(delete(RevokedToken))
    await db_session.commit()
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Get or create test user with USER role."""
    stmt = select(User).where(User.email == "standard.user@example.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email="standard.user@example.com",
            password_hash=hash_password("UserPass123!"),
            role=UserRole.USER,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    elif not user.is_active or user.role != UserRole.USER:
        user.is_active = True
        user.role = UserRole.USER
        await db_session.commit()
        await db_session.refresh(user)
    return user


@pytest.fixture
async def support_user(db_session: AsyncSession) -> User:
    """Get or create test user with SUPPORT role."""
    stmt = select(User).where(User.email == "support.agent@example.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email="support.agent@example.com",
            password_hash=hash_password("SupportPass123!"),
            role=UserRole.SUPPORT,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    elif not user.is_active or user.role != UserRole.SUPPORT:
        user.is_active = True
        user.role = UserRole.SUPPORT
        await db_session.commit()
        await db_session.refresh(user)
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Get or create test user with ADMIN role."""
    stmt = select(User).where(User.email == "admin.lead@example.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            email="admin.lead@example.com",
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
    elif not user.is_active or user.role != UserRole.ADMIN:
        user.is_active = True
        user.role = UserRole.ADMIN
        await db_session.commit()
        await db_session.refresh(user)
    return user


@pytest.fixture
def user_token(regular_user: User) -> str:
    """JWT access token for standard user."""
    token, _, _ = create_access_token(
        user_id=regular_user.id,
        email=regular_user.email,
        role=regular_user.role,
    )
    return token


@pytest.fixture
def support_token(support_user: User) -> str:
    """JWT access token for support agent."""
    token, _, _ = create_access_token(
        user_id=support_user.id,
        email=support_user.email,
        role=support_user.role,
    )
    return token


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """JWT access token for admin."""
    token, _, _ = create_access_token(
        user_id=admin_user.id,
        email=admin_user.email,
        role=admin_user.role,
    )
    return token
