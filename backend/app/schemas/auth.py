"""Auth and user schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import CustomerTier, UserRole
from app.schemas.common import ORMModel


def _clean_phone(v: str | None) -> str | None:
    if not v or not v.strip():
        return None
    stripped = v.strip()
    digits = re.sub(r"\D", "", stripped)
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone number must contain between 10 and 15 digits.")
    if stripped.startswith("+"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _clean_phone(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class CustomerProfileOut(ORMModel):
    tier: CustomerTier = CustomerTier.STANDARD
    loyalty_points: int = 0
    lifetime_value: float = 0.0
    total_orders: int = 0
    preferred_language: str = "en"
    default_address: str | None = None
    city: str | None = None
    pincode: str | None = None


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    phone: str | None = None
    role: UserRole
    is_active: bool
    avatar_url: str | None = None
    locale: str = "en-IN"
    created_at: datetime
    profile: CustomerProfileOut | None = None


class AuthResponse(BaseModel):
    user: UserOut
    tokens: TokenPair


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = None
    default_address: str | None = None
    city: str | None = None
    pincode: str | None = None
    preferred_language: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _clean_phone(v)
