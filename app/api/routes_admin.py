"""Administrative endpoints with Role-Based Access Control enforcement."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.core.token_service import revoke_all_user_tokens
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import RoleUpdate, UserRead, UserStatusUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Administration & RBAC"])


@router.get(
    "/users",
    response_model=PaginatedResponse[UserRead],
    summary="List all users (Admin & Support)",
    description="Retrieve paginated list of registered users. Accessible to ADMIN and SUPPORT roles.",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.SUPPORT))],
)
async def list_users(
    limit: int = 20,
    offset: int = 0,
    role_filter: UserRole | None = None,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserRead]:
    pagination = PaginationParams(limit=limit, offset=offset)

    base_query = select(User)
    count_query = select(func.count(User.id))

    if role_filter:
        base_query = base_query.where(User.role == role_filter)
        count_query = count_query.where(User.role == role_filter)

    total = (await db.execute(count_query)).scalar_one()

    stmt = (
        base_query.order_by(User.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    users = (await db.execute(stmt)).scalars().all()

    return PaginatedResponse(
        items=[UserRead.model_validate(u) for u in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Get user details by ID (Admin & Support)",
    description="Retrieve user profile by ID. Accessible to ADMIN and SUPPORT roles.",
    dependencies=[Depends(require_role(UserRole.ADMIN, UserRole.SUPPORT))],
)
async def get_user_by_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found",
        )
    return UserRead.model_validate(user)


@router.patch(
    "/users/{user_id}/role",
    response_model=UserRead,
    summary="Update user role (Admin Only)",
    description="Assign a new role to a user. Strictly restricted to ADMIN role. Automatically revokes existing sessions.",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def update_user_role(
    user_id: str,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found",
        )

    old_role = user.role
    user.role = payload.role

    # Security best practice: revoke all active sessions to force re-authentication with new privileges
    revoked_count = await revoke_all_user_tokens(db, user.id)
    await db.commit()
    await db.refresh(user)

    logger.info(
        f"Admin updated role for user {user.id} from {old_role} to {payload.role}. "
        f"Revoked {revoked_count} active sessions."
    )
    return UserRead.model_validate(user)


@router.patch(
    "/users/{user_id}/status",
    response_model=UserRead,
    summary="Update user active status (Admin Only)",
    description="Activate or deactivate a user account. Deactivation immediately invalidates active sessions.",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found",
        )

    user.is_active = payload.is_active

    if not payload.is_active:
        # Revoke all tokens if user deactivated
        await revoke_all_user_tokens(db, user.id)

    await db.commit()
    await db.refresh(user)

    logger.info(f"Admin updated active status for user {user.id} to {payload.is_active}")
    return UserRead.model_validate(user)
