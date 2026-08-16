"""Identity and customer profile models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import CustomerTier, UserRole

if TYPE_CHECKING:  # pragma: no cover
    from app.models.order import Order
    from app.models.support import Conversation, Ticket


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(24), default=UserRole.CUSTOMER, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    locale: Mapped[str] = mapped_column(String(12), default="en-IN")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped["CustomerProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="customer", foreign_keys="Conversation.customer_id"
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="customer", foreign_keys="Ticket.customer_id"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"


class CustomerProfile(UUIDMixin, TimestampMixin, Base):
    """Retail-specific attributes the agent uses for personalisation."""

    __tablename__ = "customer_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    tier: Mapped[str] = mapped_column(String(16), default=CustomerTier.STANDARD)
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0)
    lifetime_value: Mapped[float] = mapped_column(Float, default=0.0)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    preferred_language: Mapped[str] = mapped_column(String(12), default="en")
    default_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80))
    pincode: Mapped[str | None] = mapped_column(String(16))
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="profile")
