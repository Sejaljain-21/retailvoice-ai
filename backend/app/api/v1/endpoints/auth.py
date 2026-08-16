"""Registration, login, refresh and profile endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.exceptions import AuthError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import CustomerProfile, User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UpdateProfileRequest,
    UserOut,
)

router = APIRouter()


def _tokens_for(user: User) -> TokenPair:
    claims = {"role": user.role, "email": user.email, "name": user.full_name}
    return TokenPair(
        access_token=create_access_token(user.id, **claims),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    """Create a customer account."""
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalars().first()
    if existing:
        raise ConflictError("An account with that email already exists.")

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        role=UserRole.CUSTOMER,
    )
    user.profile = CustomerProfile()
    db.add(user)
    await db.flush()
    await db.refresh(user, ["profile"])

    return AuthResponse(user=UserOut.model_validate(user), tokens=_tokens_for(user))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    user = (
        await db.execute(
            select(User)
            .options(selectinload(User.profile))
            .where(User.email == payload.email.lower())
        )
    ).scalars().first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    return AuthResponse(user=UserOut.model_validate(user), tokens=_tokens_for(user))


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
    except Exception as exc:
        raise AuthError("Invalid refresh token.") from exc
    if claims.get("type") != "refresh":
        raise AuthError("That is not a refresh token.")

    user = (
        await db.execute(select(User).where(User.id == claims.get("sub")))
    ).scalars().first()
    if not user or not user.is_active:
        raise AuthError("Account not found.")
    return _tokens_for(user)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UpdateProfileRequest, user: CurrentUser, db: DbSession) -> UserOut:
    if payload.full_name:
        user.full_name = payload.full_name.strip()
    if payload.phone is not None:
        user.phone = payload.phone

    profile = (
        await db.execute(select(CustomerProfile).where(CustomerProfile.user_id == user.id))
    ).scalars().first()
    if profile is None:
        profile = CustomerProfile(user_id=user.id)
        db.add(profile)

    for field in ("default_address", "city", "pincode", "preferred_language"):
        value = getattr(payload, field)
        if value is not None:
            setattr(profile, field, value)

    await db.flush()
    await db.refresh(user, ["profile"])
    return UserOut.model_validate(user)
