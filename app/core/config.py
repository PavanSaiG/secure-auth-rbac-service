"""Application configuration settings for Authentication & RBAC Service."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for auth service, security policies, and DB connections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "secure-auth-service"
    ENVIRONMENT: Literal["development", "qa", "production", "test"] = "development"
    LOG_LEVEL: str = "INFO"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Persistence
    DATABASE_URL: str = "sqlite+aiosqlite:///./auth.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # JWT Cryptographic Settings
    JWT_SECRET_KEY: str = "super-secret-key-at-least-32-characters-long-for-hmac-sha256"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "secure-auth-service"
    JWT_AUDIENCE: str = "secure-api-clients"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Cookie & CORS
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = False  # Set True in production HTTPS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Rate Limiting (sliding window per minute per IP)
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10
    RATE_LIMIT_REGISTER_PER_MINUTE: int = 5
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 60


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
