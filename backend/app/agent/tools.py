"""The agent's tool belt.

Each tool is a JSON-schema'd capability the LLM may call. Handlers are plain
async functions over the database - they contain no prompt logic, so they are
independently unit-testable and reusable by the REST API.

Every handler returns a JSON-serialisable dict. Errors are returned as data
(`{"error": ...}`) rather than raised, so a failing tool never breaks the turn;
the model sees the failure and can recover or escalate.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.logging import get_logger
from app.models.catalog import Product, StoreLocation
from app.models.enums import EscalationReason, TicketPriority, UserRole
from app.models.support import Conversation
from app.models.user import CustomerProfile, User
from app.services import orders_service as orders
from app.services import rag
from app.services import tickets_service as tickets

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Execution context
# ---------------------------------------------------------------------------
@dataclass
class ToolContext:
    db: AsyncSession
    conversation: Conversation
    user: User | None = None
    language: str = "en"
    sentiment_score: float = 0.0
    intent: str = "unknown"
    # Filled in by handlers so the orchestrator can react (e.g. escalation).
    flags: dict[str, Any] = field(default_factory=dict)

    @property
    def is_staff(self) -> bool:
        return bool(
            self.user
            and self.user.role in (UserRole.AGENT, UserRole.SUPERVISOR, UserRole.ADMIN)
        )


Handler = Callable[..., Awaitable[dict[str, Any]]]
_REGISTRY: dict[str, tuple[dict[str, Any], Handler]] = {}


def tool(name: str, description: str, schema: dict[str, Any]):
    """Decorator that registers a handler together with its JSON schema."""

    def wrapper(fn: Handler) -> Handler:
        _REGISTRY[name] = (
            {"name": name, "description": description, "input_schema": schema},
            fn,
        )
        return fn

    return wrapper


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


def _str(desc: str, **extra: Any) -> dict[str, Any]:
    return {"type": "string", "description": desc, **extra}


def _int(desc: str, **extra: Any) -> dict[str, Any]:
    return {"type": "integer", "description": desc, **extra}


def _bool(desc: str) -> dict[str, Any]:
    return {"type": "boolean", "description": desc}


# `message` is customer-safe (a weak model may echo it verbatim);
# `agent_hint` carries the internal instruction that must never be spoken.
NEEDS_SIGN_IN = {
    "found": False,
    "needs_authentication": True,
    "message": (
        "I'll need you to sign in before I can pull up account or order details - "
        "or you can give me your order number and I'll look it up that way."
    ),
    "agent_hint": "Account tools are unavailable until the customer authenticates.",
}

NO_ORDER_REFERENCE = {
    "found": False,
    "missing_order_reference": True,
    "message": "Which order is this about? Your order number looks like ORD-2508123456.",
    "agent_hint": "Ask the customer for the order number, then call the tool again.",
}


async def _resolve_order(
    ctx: ToolContext,
    order_number: str | None,
    most_recent: bool,
    statuses: list[str] | None = None,
):
    """Shared order resolution with an ownership check.

    When no order number is given and the customer is signed in, fall back to
    their newest order - optionally restricted to the statuses for which the
    requested action is even valid (e.g. only delivered orders can be returned).
    """
    order = None
    if order_number:
        order = await orders.get_order_by_number(ctx.db, order_number)
    elif most_recent and ctx.user:
        order = await orders.latest_order_for(ctx.db, ctx.user.id, statuses)

    if not order:
        if not order_number:
            if not ctx.user:
                return None, dict(NEEDS_SIGN_IN)
            if statuses is orders.CANCELLABLE_STATUSES:
                return None, {
                    "found": False,
                    "message": "You don't have any orders that can still be cancelled - "
                               "everything on your account has already shipped or "
                               "been delivered.",
                    "agent_hint": "Offer a return or refuse-at-door instead.",
                }
            if statuses is orders.RETURNABLE_STATUSES:
                return None, {
                    "found": False,
                    "message": "I can't see a delivered order on your account to return. "
                               "Which order number is this about?",
                    "agent_hint": "Ask for the order number.",
                }
            return None, dict(NO_ORDER_REFERENCE)
        return None, {
            "found": False,
            "message": (
                f"I couldn't find an order matching {order_number}. Could you read the "
                "number out once more? It looks like ORD-2508123456."
            ),
            "agent_hint": "No order matched; re-confirm the reference with the customer.",
        }

    if ctx.user and not ctx.is_staff and order.customer_id != ctx.user.id:
        return None, {
            "found": False,
            "message": (
                "That order number isn't on this account. Please double-check it, or sign "
                "in with the account used to place the order."
            ),
            "authorization_failed": True,
            "agent_hint": "Ownership check failed - do not reveal any order details.",
        }
    if not ctx.user and not settings.ALLOW_ANONYMOUS_ORDER_LOOKUP:
        return None, dict(NEEDS_SIGN_IN)

    return order, None


# ===========================================================================
# Order tools
# ===========================================================================
@tool(
    "lookup_order",
    "Fetch the full status of a customer's order: items, amount, payment state, "
    "promised delivery date and tracking number. Use this for any 'where is my order', "
    "'what did I buy' or order-status question. Prefer the order number when the "
    "customer gives one; otherwise set most_recent=true for the signed-in customer.",
    _obj({
        "order_number": _str("Order reference such as ORD-2508123456."),
        "most_recent": _bool("Use the signed-in customer's latest order instead."),
    }),
)
async def lookup_order(ctx: ToolContext, order_number: str | None = None,
                       most_recent: bool = False) -> dict[str, Any]:
    order, error = await _resolve_order(ctx, order_number, most_recent or not order_number)
    if error:
        return error
    return {"found": True, "order": orders.order_snapshot(order)}


@tool(
    "track_shipment",
    "Get live courier tracking for an order: carrier, current scan location, "
    "estimated delivery and the full scan history. Also reports whether the parcel "
    "is running late. Use for delivery-status and delay questions.",
    _obj({
        "order_number": _str("Order reference."),
        "tracking_number": _str("Carrier AWB / tracking number, if the customer has it."),
        "most_recent": _bool("Track the signed-in customer's latest order."),
    }),
)
async def track_shipment(ctx: ToolContext, order_number: str | None = None,
                         tracking_number: str | None = None,
                         most_recent: bool = False) -> dict[str, Any]:
    order = None
    if tracking_number:
        order = await orders.find_order_by_tracking(ctx.db, tracking_number)
        if not order:
            return {"found": False, "message": "No shipment matches that tracking number."}
    else:
        order, error = await _resolve_order(ctx, order_number, most_recent or not order_number)
        if error:
            return error

    snapshot = orders.shipment_snapshot(order)
    if snapshot.get("is_delayed"):
        ctx.flags["delivery_delayed"] = True
    return snapshot


@tool(
    "cancel_order",
    "Cancel an order that has not shipped yet and start the refund. "
    "A valid security OTP verification (via send_security_otp and verify_security_otp) "
    "MUST be performed before cancelling. If not verified, this tool will fail and instruct "
    "you to send an OTP to the customer's registered phone.",
    _obj({
        "order_number": _str("Order reference to cancel."),
        "reason": _str("Why the customer wants to cancel."),
    }, ["order_number", "reason"]),
)
async def cancel_order(ctx: ToolContext, order_number: str = "",
                       reason: str = "Customer request") -> dict[str, Any]:
    order, error = await _resolve_order(
        ctx, order_number, not order_number, orders.CANCELLABLE_STATUSES
    )
    if error:
        return error

    # Verify that security OTP verification has been performed
    meta = ctx.conversation.conversation_metadata or {}
    is_verified = (
        ctx.flags.get("otp_verified")
        or meta.get("otp_verified")
        or meta.get("otp_verified_for") in (order.order_number, "cancel_order", True)
    )
    if not is_verified:
        phone = (ctx.user.phone if ctx.user else None)
        if not phone:
            return {
                "error": "NO_PHONE_ON_ACCOUNT",
                "requires_otp": True,
                "order_number": order.order_number,
                "message": "To cancel this order we need to send you a security code, but your account "
                           "doesn't have a mobile number registered. Please update your profile with "
                           "a valid phone number and try again.",
            }
        masked = _mask_phone(phone)
        return {
            "error": "OTP_VERIFICATION_REQUIRED",
            "requires_otp": True,
            "order_number": order.order_number,
            "masked_phone": masked,
            "message": f"Security verification required before cancelling order {order.order_number}. "
                       f"A 4-digit verification code will be dispatched to your registered mobile ({masked}). "
                       "Please ask me to send a security code first.",
        }

    result = await orders.cancel_order(ctx.db, order, reason)
    if result.get("success"):
        ctx.flags["order_cancelled"] = order.order_number
    return result


@tool(
    "initiate_return",
    "Start a return / refund for a delivered order. Validates the return window and "
    "the product's returnability, then issues an RMA number and books a free pickup. "
    "Ask for the reason before calling.",
    _obj({
        "order_number": _str("Order reference."),
        "reason": _str("Short return reason, e.g. 'Item arrived damaged'."),
        "comments": _str("Any extra detail the customer gave."),
        "order_item_id": _str("Specific line item id, when the order has several items."),
    }, ["order_number", "reason"]),
)
async def initiate_return(ctx: ToolContext, order_number: str = "", reason: str = "",
                          comments: str | None = None,
                          order_item_id: str | None = None) -> dict[str, Any]:
    order, error = await _resolve_order(
        ctx, order_number, not order_number, orders.RETURNABLE_STATUSES
    )
    if error:
        return error
    reason = reason or "Not as expected"
    result = await orders.create_return(
        ctx.db, order=order, reason=reason, comments=comments,
        order_item_id=order_item_id, by_agent=True,
    )
    if result.get("policy_blocked"):
        ctx.flags["policy_blocked"] = True
    if result.get("success"):
        ctx.flags["return_created"] = result["rma_number"]
    return result


@tool(
    "get_order_history",
    "List the signed-in customer's recent orders with status and amount. Useful when "
    "the customer cannot remember an order number.",
    _obj({"limit": _int("How many orders to return (default 5).", minimum=1, maximum=20)}),
)
async def get_order_history(ctx: ToolContext, limit: int = 5) -> dict[str, Any]:
    if not ctx.user:
        return NEEDS_SIGN_IN
    rows = await orders.list_orders(ctx.db, customer_id=ctx.user.id, limit=min(limit, 20))
    return {
        "found": bool(rows),
        "count": len(rows),
        "orders": [
            {
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": o.total_amount,
                "placed_at": o.placed_at.isoformat() if o.placed_at else None,
                "items": [i.product_name for i in o.items][:3],
            }
            for o in rows
        ],
    }


# ===========================================================================
# Catalogue tools
# ===========================================================================
def _product_payload(p: Product) -> dict[str, Any]:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "brand": p.brand,
        "price": p.price,
        "mrp": p.mrp,
        "currency": p.currency,
        "discount_percent": p.discount_percent,
        "rating": p.rating,
        "review_count": p.review_count,
        "in_stock": p.in_stock,
        "stock_quantity": p.stock_quantity,
        "return_window_days": p.return_window_days,
        "attributes": p.attributes,
        "description": (p.description or "")[:220],
    }


async def _search_products(
    db: AsyncSession, query: str, *, limit: int = 5,
    max_price: float | None = None, in_stock_only: bool = False,
) -> list[Product]:
    terms = [t for t in query.lower().split() if len(t) > 2][:6]
    stmt = select(Product).where(Product.is_active.is_(True))
    if terms:
        conditions = []
        for term in terms:
            like = f"%{term}%"
            conditions.append(
                or_(
                    Product.name.ilike(like),
                    Product.brand.ilike(like),
                    Product.description.ilike(like),
                )
            )
        stmt = stmt.where(or_(*conditions))
    if max_price:
        stmt = stmt.where(Product.price <= max_price)
    if in_stock_only:
        stmt = stmt.where(Product.stock_quantity > 0)

    rows = list((await db.execute(stmt.limit(60))).scalars().all())

    # Rank by how many query terms hit, then rating, then stock.
    def score(p: Product) -> tuple[int, float, int]:
        haystack = f"{p.name} {p.brand} {' '.join(p.tags or [])} {p.description}".lower()
        hits = sum(1 for t in terms if t in haystack)
        return (hits, p.rating, 1 if p.in_stock else 0)

    rows.sort(key=score, reverse=True)
    return rows[:limit]


@tool(
    "check_product_availability",
    "Check whether products matching a description are in stock, with live stock "
    "counts, price and rating. Use for 'do you have...', 'is X available' questions.",
    _obj({
        "query": _str("Product name, brand or description to look for."),
        "limit": _int("Maximum results (default 4).", minimum=1, maximum=10),
    }, ["query"]),
)
async def check_product_availability(ctx: ToolContext, query: str, limit: int = 4) -> dict[str, Any]:
    rows = await _search_products(ctx.db, query, limit=limit)
    return {
        "query": query,
        "count": len(rows),
        "products": [_product_payload(p) for p in rows],
    }


@tool(
    "recommend_products",
    "Recommend products for a need or budget, ranked by rating and availability. "
    "Use when the customer is shopping rather than asking about an existing order.",
    _obj({
        "query": _str("What the customer is looking for, including any preferences."),
        "max_price": {"type": "number", "description": "Budget ceiling, if stated."},
        "limit": _int("Maximum results (default 4).", minimum=1, maximum=10),
    }, ["query"]),
)
async def recommend_products(ctx: ToolContext, query: str, max_price: float | None = None,
                             limit: int = 4) -> dict[str, Any]:
    rows = await _search_products(
        ctx.db, query, limit=limit, max_price=max_price, in_stock_only=True
    )
    return {
        "query": query,
        "max_price": max_price,
        "count": len(rows),
        "products": [_product_payload(p) for p in rows],
    }


@tool(
    "check_delivery_estimate",
    "Estimate the delivery date and shipping fee for a pincode, and say whether "
    "same-day or express delivery is available there.",
    _obj({
        "pincode": _str("6-digit destination pincode."),
        "product_id": _str("Product being purchased, if known."),
    }, ["pincode"]),
)
async def check_delivery_estimate(ctx: ToolContext, pincode: str,
                                  product_id: str | None = None) -> dict[str, Any]:
    pin = "".join(c for c in pincode if c.isdigit())
    if len(pin) != 6:
        return {"serviceable": False, "message": "That doesn't look like a valid 6-digit pincode."}

    # Deterministic pseudo-logic standing in for a real serviceability API.
    bucket = int(pin) % 10
    serviceable = bucket != 7
    metro = bucket in (0, 1, 2, 3)
    days = 1 if metro else (3 if bucket < 6 else 5)

    return {
        "serviceable": serviceable,
        "pincode": pin,
        "estimated_days": days,
        "estimated_date": (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat(),
        "same_day_available": metro,
        "express_available": serviceable,
        "shipping_fee": 0.0 if metro else 49.0,
        "cod_available": serviceable and bucket != 9,
        "message": (
            f"Deliverable in about {days} day(s)." if serviceable
            else "We don't currently deliver to that pincode."
        ),
    }


@tool(
    "find_nearby_store",
    "Find physical retail stores by city or pincode, with address, phone, opening "
    "hours and whether click-and-collect is supported.",
    _obj({
        "city": _str("City name."),
        "pincode": _str("6-digit pincode."),
    }),
)
async def find_nearby_store(ctx: ToolContext, city: str | None = None,
                            pincode: str | None = None) -> dict[str, Any]:
    stmt = select(StoreLocation)
    if pincode:
        stmt = stmt.where(StoreLocation.pincode == pincode.strip())
    elif city:
        stmt = stmt.where(StoreLocation.city.ilike(f"%{city.strip()}%"))
    rows = list((await ctx.db.execute(stmt.limit(5))).scalars().all())

    if not rows and (city or pincode):
        rows = list((await ctx.db.execute(select(StoreLocation).limit(3))).scalars().all())

    return {
        "count": len(rows),
        "stores": [
            {
                "name": s.name,
                "address": s.address,
                "city": s.city,
                "pincode": s.pincode,
                "phone": s.phone,
                "opening_hours": s.opening_hours,
                "supports_pickup": s.supports_pickup,
            }
            for s in rows
        ],
    }


# ===========================================================================
# Knowledge / account tools
# ===========================================================================
@tool(
    "search_knowledge_base",
    "Search official policy and help articles (returns, refunds, shipping, warranty, "
    "payments, loyalty programme, store policies). ALWAYS use this before answering "
    "any policy question - never state a policy from memory.",
    _obj({
        "query": _str("What to look up, in the customer's own words."),
        "category": _str("Optional filter: returns, shipping, payments, warranty, account, offers."),
    }, ["query"]),
)
async def search_knowledge_base(ctx: ToolContext, query: str,
                                category: str | None = None) -> dict[str, Any]:
    hits = await rag.search(ctx.db, query, category=category)
    ctx.flags.setdefault("citations", []).extend(hits)
    return {
        "query": query,
        "count": len(hits),
        "hits": [
            {
                "title": h["title"],
                "slug": h["slug"],
                "category": h["category"],
                "snippet": h["snippet"],
                "score": h["score"],
            }
            for h in hits
        ],
    }


@tool(
    "get_customer_profile",
    "Read the signed-in customer's profile: name, loyalty tier and points, lifetime "
    "order count, saved address and their three most recent orders. Use it to "
    "personalise the conversation.",
    _obj({}),
)
async def get_customer_profile(ctx: ToolContext) -> dict[str, Any]:
    if not ctx.user:
        return NEEDS_SIGN_IN

    profile = (
        await ctx.db.execute(
            select(CustomerProfile).where(CustomerProfile.user_id == ctx.user.id)
        )
    ).scalars().first()
    recent = await orders.list_orders(ctx.db, customer_id=ctx.user.id, limit=3)

    return {
        "found": True,
        "name": ctx.user.full_name,
        "email": ctx.user.email,
        "tier": profile.tier if profile else "standard",
        "loyalty_points": profile.loyalty_points if profile else 0,
        "total_orders": profile.total_orders if profile else len(recent),
        "lifetime_value": profile.lifetime_value if profile else 0.0,
        "city": profile.city if profile else None,
        "default_address": profile.default_address if profile else None,
        "recent_orders": [
            {
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": o.total_amount,
                "placed_at": o.placed_at.isoformat() if o.placed_at else None,
            }
            for o in recent
        ],
    }


# ===========================================================================
# Service-recovery tools
# ===========================================================================
@tool(
    "create_support_ticket",
    "Log a formal support ticket for something that cannot be resolved in this "
    "conversation - a complaint, a bug, or a request needing back-office work. "
    "Returns a ticket number and the SLA the customer can quote.",
    _obj({
        "subject": _str("One-line summary of the issue."),
        "description": _str("Full detail, including anything already tried."),
        "priority": _str("low | medium | high | urgent",
                         enum=["low", "medium", "high", "urgent"]),
        "order_number": _str("Related order, if any."),
    }, ["subject", "description"]),
)
async def create_support_ticket(ctx: ToolContext, subject: str, description: str,
                                priority: str = "medium",
                                order_number: str | None = None) -> dict[str, Any]:
    order_id = None
    if order_number:
        order = await orders.get_order_by_number(ctx.db, order_number)
        order_id = order.id if order else None

    if priority not in {p.value for p in TicketPriority}:
        priority = tickets.derive_priority(ctx.intent, ctx.sentiment_score)

    ticket = await tickets.create_ticket(
        ctx.db,
        subject=subject,
        description=description,
        category=ctx.intent,
        priority=priority,
        customer_id=ctx.user.id if ctx.user else None,
        conversation_id=ctx.conversation.id,
        order_id=order_id,
        tags=["ai-created", ctx.conversation.channel],
        created_by_agent=True,
    )
    ctx.flags["ticket_created"] = ticket.ticket_number
    return {
        "success": True,
        "ticket_number": ticket.ticket_number,
        "priority": ticket.priority,
        "sla_hours": tickets.SLA_HOURS.get(ticket.priority, 24),
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
    }


@tool(
    "escalate_to_human",
    "Hand the conversation to a human agent. Call this when the customer asks for a "
    "person, when they are very upset, when the request is outside your authority, "
    "or when you have failed to help after two attempts. Never promise a human "
    "without calling this.",
    _obj({
        "reason": _str(
            "customer_request | negative_sentiment | low_confidence | policy_limit | "
            "repeated_failure | high_value_customer | tool_error",
            enum=[r.value for r in EscalationReason],
        ),
        "summary": _str("A short handover note for the human agent."),
    }, ["reason", "summary"]),
)
async def escalate_to_human(ctx: ToolContext, reason: str = "customer_request",
                            summary: str = "") -> dict[str, Any]:
    try:
        reason_enum = EscalationReason(reason)
    except ValueError:
        reason_enum = EscalationReason.CUSTOMER_REQUEST

    ticket = await tickets.escalate_conversation(
        ctx.db, ctx.conversation, reason=reason_enum, summary=summary
    )
    depth = await tickets.queue_depth(ctx.db)
    ctx.flags["escalated"] = True
    ctx.flags["escalation_reason"] = reason_enum.value
    ctx.flags["ticket_created"] = ticket.ticket_number

    return {
        "escalated": True,
        "ticket_number": ticket.ticket_number,
        "priority": ticket.priority,
        "assigned": bool(ticket.assigned_agent_id),
        "queue_position": max(1, depth),
        "estimated_wait_minutes": max(2, depth * 3),
        "message": "Conversation handed to a human agent with the full transcript attached.",
    }


@tool(
    "apply_goodwill_coupon",
    "Issue a goodwill discount voucher to make up for a genuine service failure "
    "(a late delivery, a damaged item, a repeated problem). Use sparingly and only "
    "when the failure is ours. Amounts above the policy limit are refused.",
    _obj({
        "reason": _str("Why the gesture is warranted."),
        "amount": {"type": "number", "description": "Voucher value in INR (max 500)."},
    }, ["reason"]),
)
async def apply_goodwill_coupon(ctx: ToolContext, reason: str,
                                amount: float = 200.0) -> dict[str, Any]:
    if amount > settings.GOODWILL_COUPON_MAX_VALUE:
        ctx.flags["policy_blocked"] = True
        return {
            "success": False,
            "message": (
                f"A voucher of that size exceeds your authority "
                f"(limit {settings.GOODWILL_COUPON_MAX_VALUE:.0f}). "
                "Escalate to a supervisor instead."
            ),
        }
    if not ctx.user:
        return NEEDS_SIGN_IN

    code = "SORRY" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    expires = datetime.now(timezone.utc) + timedelta(days=60)

    profile = (
        await ctx.db.execute(
            select(CustomerProfile).where(CustomerProfile.user_id == ctx.user.id)
        )
    ).scalars().first()
    if profile:
        note = f"[{datetime.now(timezone.utc):%Y-%m-%d}] Goodwill {code} ({amount:.0f}): {reason}"
        profile.notes = f"{profile.notes}\n{note}" if profile.notes else note

    meta = dict(ctx.conversation.conversation_metadata or {})
    meta.setdefault("goodwill_coupons", []).append(
        {"code": code, "value": amount, "reason": reason}
    )
    ctx.conversation.conversation_metadata = meta
    ctx.flags["goodwill_issued"] = code

    return {
        "success": True,
        "code": code,
        "value": amount,
        "expires_at": expires.isoformat(),
        "usage": "Applies to any order above the voucher value; single use.",
    }


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "+91 99****4321"
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) >= 10:
        return f"+91 {digits[-10:-6]}****{digits[-4:]}"
    return f"+91 ****{phone[-4:]}" if len(phone) >= 4 else "+91 99****4321"


def _mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "c****@example.com"
    user_part, domain = email.split("@", 1)
    return f"{user_part[:2]}***@{domain}"


@tool(
    "send_security_otp",
    "Dispatch a simulated 4-digit security verification code via SMS to the customer's "
    "registered mobile number/email. Call this whenever a customer requests an order cancellation, "
    "high-value return, or bank refund. Never perform a sensitive cancellation without calling this first.",
    _obj({
        "action": _str("Operation requiring verification, e.g. 'cancel_order', 'initiate_return'."),
        "order_number": _str("Order reference number."),
        "destination": _str("Optional phone number or email if not already on the customer account."),
    }, ["action"]),
)
async def send_security_otp(ctx: ToolContext, action: str = "cancel_order",
                            order_number: str | None = None,
                            destination: str | None = None) -> dict[str, Any]:
    # Look up registered phone and email from the logged-in customer account
    phone = destination or (ctx.user.phone if ctx.user else None)
    email = (ctx.user.email if ctx.user else None)

    # If no phone is available and no explicit destination given, we cannot send an OTP
    if not phone:
        return {
            "otp_dispatched": False,
            "error": "NO_PHONE_REGISTERED",
            "message": (
                "Your account doesn't have a mobile number on file. Please update your profile "
                "with a valid phone number so we can send you the security verification code."
            ),
        }

    masked_phone = _mask_phone(phone)
    masked_email = _mask_email(email) if email else "(no email on file)"

    # Generate a live dynamic 4-digit code (e.g. 5824, 7193, 8312)
    code = f"{random.randint(1000, 9999)}"
    meta = dict(ctx.conversation.conversation_metadata or {})
    meta["pending_otp"] = {
        "code": code,
        "action": action,
        "order_number": order_number,
        "masked_phone": masked_phone,
        "masked_email": masked_email,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ctx.conversation.conversation_metadata = meta
    flag_modified(ctx.conversation, "conversation_metadata")
    await ctx.db.flush()

    return {
        "otp_dispatched": True,
        "action": action,
        "order_number": order_number,
        "destination": masked_phone,
        "masked_phone": masked_phone,
        "masked_email": masked_email,
        "live_code": code,
        "message": (
            f"A 4-digit verification code has been dispatched to your registered "
            f"mobile number ({masked_phone}). Please confirm the code to complete authorization."
        ),
    }


@tool(
    "verify_security_otp",
    "Verify the 4-digit security OTP code entered or spoken by the customer against the live code "
    "dispatched to their phone/email. Only call this after the customer provides their code.",
    _obj({
        "code": _str("The 4-digit verification code spoken or entered by the customer."),
        "action": _str("The operation being verified, e.g. 'cancel_order', 'bank_refund', 'initiate_return'."),
        "order_number": _str("Order reference number if applicable."),
    }, ["code"]),
)
async def verify_security_otp(ctx: ToolContext, code: str, action: str = "cancel_order",
                              order_number: str | None = None) -> dict[str, Any]:
    clean_code = "".join(ch for ch in str(code) if ch.isdigit())
    meta = dict(ctx.conversation.conversation_metadata or {})
    pending = meta.get("pending_otp") or {}
    expected_code = pending.get("code")

    if not clean_code:
        return {
            "verified": False,
            "message": "Please enter the 4-digit verification code sent to your mobile.",
            "status": "VERIFICATION_FAILED",
        }
    if not expected_code:
        return {
            "verified": False,
            "message": "No active security code was found for this session. Please ask me to send a new one.",
            "status": "NO_PENDING_OTP",
        }
    if clean_code != expected_code:
        return {
            "verified": False,
            "message": f"Incorrect code. Please re-check the 4-digit SMS code sent to {pending.get('masked_phone', 'your mobile')}.",
            "status": "VERIFICATION_FAILED",
        }

    target_order = order_number or pending.get("order_number")
    ctx.flags["otp_verified"] = True
    meta["otp_verified"] = True
    meta["otp_verified_for"] = target_order or action or True
    if "pending_otp" in meta:
        del meta["pending_otp"]
    ctx.conversation.conversation_metadata = meta
    flag_modified(ctx.conversation, "conversation_metadata")
    await ctx.db.flush()

    return {
        "verified": True,
        "code": clean_code,
        "action": action,
        "order_number": target_order,
        "message": f"Security verification code {clean_code} successfully verified for {action}.",
        "status": "AUTHORIZATION_GRANTED",
    }


@tool(
    "record_csat_feedback",
    "Record the customer's post-resolution CSAT satisfaction score (1 to 5) into the analytics database. "
    "Call this when the customer responds to the satisfaction survey question.",
    _obj({
        "rating": _int("Customer satisfaction rating from 1 to 5.", minimum=1, maximum=5),
        "comment": _str("Customer's feedback comment or verbal sentiment reason."),
        "resolved": _bool("Whether the customer's inquiry was successfully resolved."),
    }, ["rating"]),
)
async def record_csat_feedback(ctx: ToolContext, rating: int, comment: str | None = None,
                               resolved: bool = True) -> dict[str, Any]:
    from app.models.support import Feedback
    rating_val = max(1, min(5, int(rating)))
    existing = (
        await ctx.db.execute(select(Feedback).where(Feedback.conversation_id == ctx.conversation.id))
    ).scalars().first()
    if existing:
        existing.rating = rating_val
        existing.comment = comment or existing.comment
        existing.resolved = resolved
    else:
        ctx.db.add(Feedback(
            conversation_id=ctx.conversation.id,
            rating=rating_val,
            resolved=resolved,
            comment=comment or "Captured via automated voice survey",
        ))
    await ctx.db.flush()
    return {
        "success": True,
        "rating": rating_val,
        "message": f"Customer satisfaction score {rating_val}/5 recorded in analytics records.",
    }



# ===========================================================================
# Registry access
# ===========================================================================
def tool_schemas() -> list[dict[str, Any]]:
    return [schema for schema, _ in _REGISTRY.values()]


def tool_names() -> list[str]:
    return list(_REGISTRY.keys())


def get_handler(name: str) -> Handler | None:
    entry = _REGISTRY.get(name)
    return entry[1] if entry else None


async def execute(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    handler = get_handler(name)
    if handler is None:
        return {"error": f"Unknown tool '{name}'.", "available": tool_names()}
    try:
        clean = {k: v for k, v in (arguments or {}).items() if v is not None}
        return await handler(ctx, **clean)
    except TypeError as exc:
        log.warning("Tool %s called with bad arguments %s: %s", name, arguments, exc)
        return {"error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 - surfaced to the model as data
        log.exception("Tool %s failed", name)
        ctx.flags["tool_error"] = name
        return {"error": f"{name} failed: {exc}"}
