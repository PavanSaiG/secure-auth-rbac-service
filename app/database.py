"""Database engine and session management for Authentication Service."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all database models."""

    pass


def create_engine_instance() -> AsyncEngine:
    """Build async SQLAlchemy engine based on configuration."""
    settings = get_settings()
    db_url = settings.DATABASE_URL

    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {
        "echo": settings.DB_ECHO,
        "future": True,
    }

    if "sqlite" in db_url:
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args
    else:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        engine_kwargs["pool_pre_ping"] = True

    return create_async_engine(db_url, **engine_kwargs)


engine = create_engine_instance()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency yielding active async database session with automatic transaction management."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all registered database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close and dispose database engine connection pools."""
    await engine.dispose()
