"""Order domain logic shared by the REST API and the agent's tools."""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError_
from app.models.catalog import Product
from app.models.enums import (
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    ShipmentStatus,
)
from app.models.order import Order, OrderItem, ReturnRequest, Shipment
from app.models.user import CustomerProfile, User

TAX_RATE = 0.18
FREE_SHIPPING_THRESHOLD = 999.0
STANDARD_SHIPPING_FEE = 49.0

COUPONS: dict[str, dict] = {
    "WELCOME10": {"type": "percent", "value": 10, "max_discount": 500, "min_order": 999},
    "FESTIVE500": {"type": "flat", "value": 500, "max_discount": 500, "min_order": 2999},
    "FREESHIP": {"type": "shipping", "value": 0, "max_discount": 0, "min_order": 0},
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_order_number() -> str:
    return f"ORD-{_now():%y%m}{''.join(random.choices(string.digits, k=6))}"


def generate_tracking_number(carrier: str = "BLDT") -> str:
    return f"{carrier[:4].upper()}{''.join(random.choices(string.digits, k=9))}"


def generate_rma_number() -> str:
    return f"RMA-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _order_query():
    return select(Order).options(
        selectinload(Order.items),
        selectinload(Order.shipment),
        selectinload(Order.returns),
    )


async def get_order_by_number(db: AsyncSession, order_number: str) -> Order | None:
    normalized = order_number.strip().upper().replace(" ", "")
    if normalized.startswith("#"):
        normalized = normalized[1:]
    if normalized.isdigit():
        # A bare numeric suffix (customers often read out only the digits).
        stmt = _order_query().where(Order.order_number.like(f"%{normalized}"))
    else:
        stmt = _order_query().where(Order.order_number == normalized)
    return (await db.execute(stmt)).scalars().first()


async def get_order(db: AsyncSession, order_id: str) -> Order | None:
    return (await db.execute(_order_query().where(Order.id == order_id))).scalars().first()


async def list_orders(
    db: AsyncSession,
    *,
    customer_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[Order]:
    stmt = _order_query().order_by(desc(Order.created_at)).limit(limit).offset(offset)
    if customer_id:
        stmt = stmt.where(Order.customer_id == customer_id)
    if status:
        stmt = stmt.where(Order.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def latest_order_for(
    db: AsyncSession,
    customer_id: str,
    statuses: list[str] | None = None,
) -> Order | None:
    """Most recent order, optionally restricted to a set of statuses.

    Used when a customer says "cancel my order" without giving a number - we
    resolve to the newest order that the requested action is actually valid for.
    """
    stmt = _order_query().where(Order.customer_id == customer_id)
    if statuses:
        stmt = stmt.where(Order.status.in_(statuses))
    stmt = stmt.order_by(desc(Order.created_at)).limit(1)
    return (await db.execute(stmt)).scalars().first()


CANCELLABLE_STATUSES = [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PACKED]
RETURNABLE_STATUSES = [OrderStatus.DELIVERED]


async def find_order_by_tracking(db: AsyncSession, tracking_number: str) -> Order | None:
    stmt = select(Shipment).where(Shipment.tracking_number == tracking_number.strip().upper())
    shipment = (await db.execute(stmt)).scalars().first()
    return await get_order(db, shipment.order_id) if shipment else None


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
def apply_coupon(subtotal: float, code: str | None) -> tuple[float, bool]:
    """Returns (discount_amount, free_shipping)."""
    if not code:
        return 0.0, False
    rule = COUPONS.get(code.strip().upper())
    if not rule or subtotal < rule["min_order"]:
        return 0.0, False
    if rule["type"] == "shipping":
        return 0.0, True
    if rule["type"] == "flat":
        return float(min(rule["value"], subtotal)), False
    discount = subtotal * rule["value"] / 100
    return float(min(discount, rule["max_discount"])), False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
async def create_order(
    db: AsyncSession,
    *,
    customer: User,
    lines: list[tuple[str, int]],
    shipping_address: str,
    shipping_city: str | None = None,
    shipping_pincode: str | None = None,
    payment_method: str = "upi",
    coupon_code: str | None = None,
) -> Order:
    if not lines:
        raise ValidationError_("An order needs at least one item.")

    order = Order(
        order_number=generate_order_number(),
        customer_id=customer.id,
        status=OrderStatus.CONFIRMED,
        payment_status=PaymentStatus.PAID if payment_method != "cod" else PaymentStatus.PENDING,
        payment_method=payment_method,
        shipping_address=shipping_address,
        shipping_city=shipping_city,
        shipping_pincode=shipping_pincode,
        placed_at=_now(),
        expected_delivery=_now() + timedelta(days=random.randint(2, 6)),
        coupon_code=coupon_code,
    )

    subtotal = 0.0
    for product_id, quantity in lines:
        product = (
            await db.execute(select(Product).where(Product.id == product_id))
        ).scalars().first()
        if not product:
            raise NotFoundError(f"Product {product_id} does not exist.")
        if product.stock_quantity < quantity:
            raise ConflictError(
                f"Only {product.stock_quantity} unit(s) of {product.name} are in stock."
            )
        line_total = round(product.price * quantity, 2)
        subtotal += line_total
        product.stock_quantity -= quantity
        order.items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                sku=product.sku,
                quantity=quantity,
                unit_price=product.price,
                line_total=line_total,
                attributes=dict(product.attributes or {}),
            )
        )

    discount, free_shipping = apply_coupon(subtotal, coupon_code)
    taxable = max(0.0, subtotal - discount)
    shipping = 0.0 if (free_shipping or taxable >= FREE_SHIPPING_THRESHOLD) else STANDARD_SHIPPING_FEE

    order.subtotal = round(subtotal, 2)
    order.discount = round(discount, 2)
    order.tax = round(taxable * TAX_RATE, 2)
    order.shipping_fee = shipping
    order.total_amount = round(taxable + order.tax + shipping, 2)

    db.add(order)

    profile = (
        await db.execute(select(CustomerProfile).where(CustomerProfile.user_id == customer.id))
    ).scalars().first()
    if profile:
        profile.total_orders += 1
        profile.lifetime_value = round(profile.lifetime_value + order.total_amount, 2)
        profile.loyalty_points += int(order.total_amount // 100)

    await db.flush()
    await db.refresh(order, ["items"])
    return order


async def cancel_order(db: AsyncSession, order: Order, reason: str) -> dict:
    if order.status == OrderStatus.CANCELLED:
        return {
            "success": False,
            "order_number": order.order_number,
            "message": "That order was already cancelled.",
        }
    if not order.is_cancellable:
        return {
            "success": False,
            "order_number": order.order_number,
            "status": order.status,
            "message": (
                f"Order {order.order_number} is already {order.status.replace('_', ' ')} and can no "
                "longer be cancelled. It can be returned after delivery, or you may refuse it "
                "at the door."
            ),
        }

    order.status = OrderStatus.CANCELLED
    order.cancelled_at = _now()
    order.cancellation_reason = reason
    if order.payment_status == PaymentStatus.PAID:
        order.payment_status = PaymentStatus.REFUNDED

    # Restock
    for item in order.items:
        product = (
            await db.execute(select(Product).where(Product.id == item.product_id))
        ).scalars().first()
        if product:
            product.stock_quantity += item.quantity

    if order.shipment:
        order.shipment.status = ShipmentStatus.RETURNING

    await db.flush()
    return {
        "success": True,
        "order_number": order.order_number,
        "refund_amount": order.total_amount,
        "refund_eta_days": 5,
        "message": f"Order {order.order_number} has been cancelled.",
    }


async def create_return(
    db: AsyncSession,
    *,
    order: Order,
    reason: str,
    comments: str | None = None,
    order_item_id: str | None = None,
    by_agent: bool = False,
) -> dict:
    if order.status != OrderStatus.DELIVERED:
        return {
            "success": False,
            "message": (
                f"Order {order.order_number} hasn't been delivered yet (it is "
                f"{order.status.replace('_', ' ')}), so a return can't be started. "
                "If you no longer want it, I can cancel the order instead."
            ),
        }

    existing = [r for r in order.returns if r.status not in (ReturnStatus.REJECTED,)]
    if existing:
        return {
            "success": False,
            "rma_number": existing[0].rma_number,
            "message": (
                f"A return is already in progress for this order "
                f"(RMA {existing[0].rma_number}, status "
                f"{existing[0].status.replace('_', ' ')})."
            ),
        }

    item = None
    if order_item_id:
        item = next((i for i in order.items if i.id == order_item_id), None)
    if item is None and order.items:
        item = order.items[0]

    # Return window check against the product policy.
    delivered = order.delivered_at or order.updated_at
    if delivered and delivered.tzinfo is None:
        delivered = delivered.replace(tzinfo=timezone.utc)
    window_days = 7
    if item:
        product = (
            await db.execute(select(Product).where(Product.id == item.product_id))
        ).scalars().first()
        if product:
            if not product.is_returnable:
                return {
                    "success": False,
                    "message": (
                        f"{product.name} is a non-returnable item under our policy. "
                        "If it arrived damaged or defective I can raise a replacement "
                        "request instead - would you like that?"
                    ),
                }
            window_days = product.return_window_days

    if delivered and _now() - delivered > timedelta(days=window_days):
        return {
            "success": False,
            "message": (
                f"The {window_days}-day return window for this order closed on "
                f"{(delivered + timedelta(days=window_days)):%d %b %Y}. "
                "I can still raise an exception request for a human to review - shall I?"
            ),
            "policy_blocked": True,
        }

    refund_amount = item.line_total if item else order.total_amount
    rma = ReturnRequest(
        rma_number=generate_rma_number(),
        order_id=order.id,
        order_item_id=item.id if item else None,
        customer_id=order.customer_id,
        reason=reason,
        comments=comments,
        status=ReturnStatus.APPROVED,
        refund_amount=round(float(refund_amount), 2),
        pickup_scheduled_at=_now() + timedelta(days=2),
        created_by_agent=by_agent,
    )
    db.add(rma)
    await db.flush()

    return {
        "success": True,
        "rma_number": rma.rma_number,
        "order_number": order.order_number,
        "item": item.product_name if item else None,
        "refund_amount": rma.refund_amount,
        "refund_method": rma.refund_method,
        "pickup_scheduled_at": rma.pickup_scheduled_at.isoformat(),
        "message": "Return approved and pickup scheduled.",
    }


# ---------------------------------------------------------------------------
# Shipment view
# ---------------------------------------------------------------------------
def shipment_snapshot(order: Order) -> dict:
    shipment = order.shipment
    if not shipment:
        return {
            "found": False,
            "order_number": order.order_number,
            "order_status": order.status,
            "message": (
                f"Order {order.order_number} is {order.status.replace('_', ' ')} and hasn't "
                "been handed to the courier yet."
            ),
        }

    eta = shipment.estimated_delivery
    if eta and eta.tzinfo is None:
        eta = eta.replace(tzinfo=timezone.utc)
    is_delayed = bool(
        eta
        and eta < _now()
        and shipment.status != ShipmentStatus.DELIVERED
    )

    return {
        "found": True,
        "order_number": order.order_number,
        "tracking_number": shipment.tracking_number,
        "carrier": shipment.carrier,
        "status": shipment.status,
        "current_location": shipment.current_location,
        "estimated_delivery": eta.isoformat() if eta else None,
        "delivered_at": shipment.delivered_at.isoformat() if shipment.delivered_at else None,
        "is_delayed": is_delayed,
        "events": shipment.events or [],
    }


def order_snapshot(order: Order) -> dict:
    """Compact JSON the LLM can reason over without blowing the context window."""
    return {
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "payment_method": order.payment_method,
        "total_amount": order.total_amount,
        "currency": order.currency,
        "placed_at": order.placed_at.isoformat() if order.placed_at else None,
        "expected_delivery": (
            order.expected_delivery.isoformat() if order.expected_delivery else None
        ),
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "shipping_city": order.shipping_city,
        "is_cancellable": order.is_cancellable,
        "tracking_number": order.shipment.tracking_number if order.shipment else None,
        "items": [
            {
                "id": i.id,
                "name": i.product_name,
                "sku": i.sku,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "line_total": i.line_total,
            }
            for i in order.items
        ],
        "returns": [
            {"rma_number": r.rma_number, "status": r.status, "refund_amount": r.refund_amount}
            for r in order.returns
        ],
    }


def refund_within_policy(amount: float) -> bool:
    return amount <= settings.ESCALATION_REFUND_AMOUNT_LIMIT
