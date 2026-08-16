"""Order, shipment and return schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, PaymentStatus, ReturnStatus, ShipmentStatus
from app.schemas.common import ORMModel


class OrderItemOut(ORMModel):
    id: str
    product_id: str
    product_name: str
    sku: str
    quantity: int
    unit_price: float
    line_total: float
    attributes: dict[str, Any] = Field(default_factory=dict)


class ShipmentOut(ORMModel):
    id: str
    tracking_number: str
    carrier: str
    status: ShipmentStatus
    current_location: str | None = None
    estimated_delivery: datetime | None = None
    delivered_at: datetime | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)


class ReturnRequestOut(ORMModel):
    id: str
    rma_number: str
    order_id: str
    reason: str
    comments: str | None = None
    status: ReturnStatus
    refund_amount: float
    refund_method: str
    pickup_scheduled_at: datetime | None = None
    created_at: datetime


class OrderOut(ORMModel):
    id: str
    order_number: str
    customer_id: str
    status: OrderStatus
    payment_status: PaymentStatus
    payment_method: str
    subtotal: float
    shipping_fee: float
    discount: float
    tax: float
    total_amount: float
    currency: str
    shipping_address: str
    shipping_city: str | None = None
    shipping_pincode: str | None = None
    placed_at: datetime | None = None
    expected_delivery: datetime | None = None
    delivered_at: datetime | None = None
    cancellation_reason: str | None = None
    coupon_code: str | None = None
    items: list[OrderItemOut] = Field(default_factory=list)
    shipment: ShipmentOut | None = None
    returns: list[ReturnRequestOut] = Field(default_factory=list)


class CartLine(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1, le=20)


class CreateOrderRequest(BaseModel):
    items: list[CartLine] = Field(min_length=1)
    shipping_address: str
    shipping_city: str | None = None
    shipping_pincode: str | None = None
    payment_method: str = "upi"
    coupon_code: str | None = None


class CancelOrderRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class CreateReturnRequest(BaseModel):
    order_item_id: str | None = None
    reason: str = Field(min_length=3, max_length=120)
    comments: str | None = None
