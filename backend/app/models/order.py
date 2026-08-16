"""Orders, line items, shipments, returns and refunds."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    ShipmentStatus,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.models.catalog import Product
    from app.models.user import User


class Order(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    status: Mapped[str] = mapped_column(String(24), default=OrderStatus.PENDING, index=True)
    payment_status: Mapped[str] = mapped_column(String(24), default=PaymentStatus.PENDING)
    payment_method: Mapped[str] = mapped_column(String(32), default="upi")

    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    shipping_fee: Mapped[float] = mapped_column(Float, default=0.0)
    discount: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(4), default="INR")

    shipping_address: Mapped[str] = mapped_column(Text, default="")
    shipping_city: Mapped[str | None] = mapped_column(String(80))
    shipping_pincode: Mapped[str | None] = mapped_column(String(16))

    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expected_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    coupon_code: Mapped[str | None] = mapped_column(String(32))

    customer: Mapped["User"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    shipment: Mapped["Shipment | None"] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    returns: Mapped[list["ReturnRequest"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def is_cancellable(self) -> bool:
        return self.status in {
            OrderStatus.PENDING,
            OrderStatus.CONFIRMED,
            OrderStatus.PACKED,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Order {self.order_number} {self.status}>"


class OrderItem(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)

    product_name: Mapped[str] = mapped_column(String(240))
    sku: Mapped[str] = mapped_column(String(48))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    line_total: Mapped[float] = mapped_column(Float, default=0.0)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")


class Shipment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shipments"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True, index=True
    )
    tracking_number: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    carrier: Mapped[str] = mapped_column(String(64), default="BlueDart")
    status: Mapped[str] = mapped_column(String(24), default=ShipmentStatus.LABEL_CREATED)
    current_location: Mapped[str | None] = mapped_column(String(160))
    estimated_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # [{"at": iso8601, "status": "...", "location": "..."}]
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    order: Mapped["Order"] = relationship(back_populates="shipment")


class ReturnRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "return_requests"

    rma_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[str | None] = mapped_column(ForeignKey("order_items.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    reason: Mapped[str] = mapped_column(String(120))
    comments: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=ReturnStatus.REQUESTED, index=True)
    refund_amount: Mapped[float] = mapped_column(Float, default=0.0)
    refund_method: Mapped[str] = mapped_column(String(32), default="original_payment_method")
    pickup_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_agent: Mapped[bool] = mapped_column(default=False)

    order: Mapped["Order"] = relationship(back_populates="returns")
