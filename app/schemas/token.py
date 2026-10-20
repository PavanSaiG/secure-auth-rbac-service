"""Pydantic schemas for JWT tokens and authentication responses."""

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class TokenResponse(BaseModel):
    """Access token and refresh token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Refresh token rotation request."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Decoded and verified JWT claims."""

    sub: str
    email: str
    role: UserRole
    jti: str
    exp: int
    iat: int
    iss: str
    aud: str

    model_config = ConfigDict(extra="ignore")
