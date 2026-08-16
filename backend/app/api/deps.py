"""Shared FastAPI dependencies: current user, role guards, pagination."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthError, PermissionError_
from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import PaginationParams

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_token(db: AsyncSession, token: str) -> User:
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session has expired. Please sign in again.") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid authentication token.") from exc

    if payload.get("type") != "access":
        raise AuthError("A refresh token cannot be used to access resources.")

    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.id == payload.get("sub"))
        )
    ).scalars().first()

    if not user:
        raise AuthError("The account linked to this token no longer exists.")
    if not user.is_active:
        raise PermissionError_("This account has been deactivated.")
    return user


async def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthError("Authentication required.")
    return await _user_from_token(db, credentials.credentials)


async def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> User | None:
    """Endpoints that work for both signed-in customers and anonymous visitors."""
    if credentials is None or not credentials.credentials:
        return None
    try:
        return await _user_from_token(db, credentials.credentials)
    except (AuthError, PermissionError_):
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole):
    async def guard(user: CurrentUser) -> User:
        if user.role not in {r.value for r in roles}:
            raise PermissionError_(
                f"This action requires one of these roles: {', '.join(r.value for r in roles)}."
            )
        return user

    return guard


StaffUser = Annotated[
    User, Depends(require_roles(UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN))
]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


def pagination(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


Pagination = Annotated[PaginationParams, Depends(pagination)]


async def user_from_query_token(db: AsyncSession, token: str | None) -> User | None:
    """WebSockets cannot send Authorization headers from the browser, so the
    token arrives as a query parameter instead."""
    if not token:
        return None
    try:
        return await _user_from_token(db, token)
    except (AuthError, PermissionError_):
        return None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
