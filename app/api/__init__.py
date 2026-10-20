"""API routers package."""

from fastapi import APIRouter

from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.routes_health import router as health_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)

__all__ = ["admin_router", "api_v1_router", "auth_router", "health_router"]
