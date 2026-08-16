"""Seeds a realistic demo dataset: staff and customers, catalogue, stores,
orders across every lifecycle state, the knowledge base (embedded), and a
back-dated conversation history so the analytics dashboard has real shape.

Run standalone with:  python -m app.db.seed  [--reset]
"""

from __future__ import annotations

import argparse
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.seed_data import CATEGORIES, KB_ARTICLES, PRODUCTS, STORES
from app.db.session import SessionLocal
from app.models.catalog import Category, Product, StoreLocation
from app.models.enums import (
    ChannelType,
    ConversationStatus,
    CustomerTier,
    EscalationReason,
    Intent,
    MessageRole,
    OrderStatus,
    PaymentStatus,
    ReturnStatus,
    Sentiment,
    ShipmentStatus,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.knowledge import KBDocument
from app.models.order import Order, OrderItem, ReturnRequest, Shipment
from app.models.support import Conversation, Feedback, Message, Ticket, ToolCallLog
from app.models.user import CustomerProfile, User
from app.services import rag
from app.services.orders_service import (
    generate_order_number,
    generate_rma_number,
    generate_tracking_number,
)

log = get_logger(__name__)
rng = random.Random(20250816)      # fixed seed -> reproducible demo data


def _now() -> datetime:
    return datetime.now(timezone.utc)


def slugify(title: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:120]


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
STAFF = [
    ("admin@retailvoice.ai", "Priya Menon", UserRole.ADMIN),
    ("supervisor@retailvoice.ai", "Rahul Iyer", UserRole.SUPERVISOR),
    ("agent1@retailvoice.ai", "Sneha Kulkarni", UserRole.AGENT),
    ("agent2@retailvoice.ai", "Imran Sheikh", UserRole.AGENT),
]

CUSTOMERS = [
    ("customer@retailvoice.ai", "Aarav Sharma", CustomerTier.GOLD, "Bengaluru", "560095",
     "402, Lakeview Apartments, 5th Cross, Koramangala"),
    ("meera.nair@example.com", "Meera Nair", CustomerTier.PLATINUM, "Mumbai", "400053",
     "18B, Sea Breeze CHS, Lokhandwala, Andheri West"),
    ("vikram.rao@example.com", "Vikram Rao", CustomerTier.SILVER, "Hyderabad", "500034",
     "Flat 703, Emerald Heights, Road No. 12, Banjara Hills"),
    ("fatima.k@example.com", "Fatima Khan", CustomerTier.STANDARD, "Delhi", "110001",
     "C-24, Ground Floor, Connaught Lane"),
    ("john.dsouza@example.com", "John D'Souza", CustomerTier.STANDARD, "Chennai", "600040",
     "9, Third Avenue, Anna Nagar East"),
]

DEMO_PASSWORD = "Demo@1234"


async def seed_users(db: AsyncSession) -> dict[str, User]:
    users: dict[str, User] = {}

    for email, name, role in STAFF:
        password = (
            settings.DEMO_ADMIN_PASSWORD if role == UserRole.ADMIN else DEMO_PASSWORD
        )
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=name,
            role=role,
            phone=f"+9198{rng.randint(10000000, 99999999)}",
        )
        db.add(user)
        users[email] = user

    for email, name, tier, city, pincode, address in CUSTOMERS:
        user = User(
            email=email,
            hashed_password=hash_password(DEMO_PASSWORD),
            full_name=name,
            role=UserRole.CUSTOMER,
            phone=f"+9199{rng.randint(10000000, 99999999)}",
        )
        user.profile = CustomerProfile(
            tier=tier,
            city=city,
            pincode=pincode,
            default_address=f"{address}, {city} {pincode}",
            loyalty_points=rng.randint(120, 4200),
            marketing_opt_in=rng.choice([True, False]),
        )
        db.add(user)
        users[email] = user

    await db.flush()
    log.info("Seeded %d users (%d staff, %d customers).",
             len(users), len(STAFF), len(CUSTOMERS))
    return users


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
async def seed_catalog(db: AsyncSession) -> list[Product]:
    categories: dict[str, Category] = {}
    for data in CATEGORIES:
        category = Category(**data)
        db.add(category)
        categories[data["slug"]] = category
    await db.flush()

    products: list[Product] = []
    for item in PRODUCTS:
        product = Product(
            sku=item["sku"],
            name=item["name"],
            brand=item["brand"],
            description=item["description"],
            category_id=categories[item["category"]].id,
            price=float(item["price"]),
            mrp=float(item["mrp"]),
            stock_quantity=item["stock"],
            rating=item["rating"],
            review_count=item["reviews"],
            return_window_days=item["return_days"],
            is_returnable=item.get("returnable", True),
            tags=item["tags"],
            attributes=item["attributes"],
            image_url=f"https://picsum.photos/seed/{item['sku']}/600/600",
        )
        db.add(product)
        products.append(product)

    for store in STORES:
        db.add(StoreLocation(**store))

    await db.flush()
    log.info("Seeded %d categories, %d products, %d stores.",
             len(categories), len(products), len(STORES))
    return products


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
CARRIERS = ["BlueDart", "Delhivery", "Ekart", "XpressBees"]

TRACKING_FLOW = {
    ShipmentStatus.IN_TRANSIT: ["Picked up", "In transit"],
    ShipmentStatus.OUT_FOR_DELIVERY: ["Picked up", "In transit", "Arrived at destination hub",
                                      "Out for delivery"],
    ShipmentStatus.DELIVERED: ["Picked up", "In transit", "Arrived at destination hub",
                               "Out for delivery", "Delivered"],
    ShipmentStatus.EXCEPTION: ["Picked up", "In transit", "Delivery attempt failed"],
}

# (status, days_ago, needs_shipment)
ORDER_PLAN = [
    (OrderStatus.DELIVERED, 12, True),
    (OrderStatus.DELIVERED, 6, True),
    (OrderStatus.DELIVERED, 3, True),
    (OrderStatus.OUT_FOR_DELIVERY, 3, True),
    (OrderStatus.SHIPPED, 2, True),
    (OrderStatus.SHIPPED, 9, True),          # deliberately late -> delay demo
    (OrderStatus.PACKED, 1, False),
    (OrderStatus.CONFIRMED, 0, False),
    (OrderStatus.CANCELLED, 8, False),
    (OrderStatus.DELIVERED, 25, True),       # outside the return window
]


async def seed_orders(
    db: AsyncSession, users: dict[str, User], products: list[Product]
) -> list[Order]:
    customers = [u for u in users.values() if u.role == UserRole.CUSTOMER]
    orders: list[Order] = []

    for index, (status, days_ago, needs_shipment) in enumerate(ORDER_PLAN):
        customer = customers[index % len(customers)]
        profile = customer.profile
        placed_at = _now() - timedelta(days=days_ago, hours=rng.randint(0, 20))

        chosen = rng.sample(products, rng.randint(1, 3))
        order = Order(
            order_number=generate_order_number(),
            customer_id=customer.id,
            status=status,
            payment_method=rng.choice(["upi", "card", "netbanking", "cod"]),
            shipping_address=profile.default_address or "",
            shipping_city=profile.city,
            shipping_pincode=profile.pincode,
            placed_at=placed_at,
            expected_delivery=placed_at + timedelta(days=rng.randint(2, 5)),
        )

        subtotal = 0.0
        for product in chosen:
            quantity = rng.randint(1, 2)
            line_total = round(product.price * quantity, 2)
            subtotal += line_total
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

        order.subtotal = round(subtotal, 2)
        order.shipping_fee = 0.0 if subtotal >= 999 else 49.0
        order.tax = round(subtotal * 0.18, 2)
        order.total_amount = round(subtotal + order.tax + order.shipping_fee, 2)

        if status == OrderStatus.CANCELLED:
            order.payment_status = PaymentStatus.REFUNDED
            order.cancelled_at = placed_at + timedelta(hours=6)
            order.cancellation_reason = "Ordered the wrong variant"
        elif order.payment_method == "cod" and status != OrderStatus.DELIVERED:
            order.payment_status = PaymentStatus.PENDING
        else:
            order.payment_status = PaymentStatus.PAID

        if status == OrderStatus.DELIVERED:
            order.delivered_at = placed_at + timedelta(days=rng.randint(2, 4))

        db.add(order)
        await db.flush()

        if needs_shipment:
            shipment_status = {
                OrderStatus.DELIVERED: ShipmentStatus.DELIVERED,
                OrderStatus.OUT_FOR_DELIVERY: ShipmentStatus.OUT_FOR_DELIVERY,
                OrderStatus.SHIPPED: ShipmentStatus.IN_TRANSIT,
            }[status]

            hubs = ["Bengaluru Hub", "Chennai Sorting Centre", "Mumbai Gateway",
                    "Delhi NCR Hub", "Hyderabad Hub"]
            events = []
            for step, label in enumerate(TRACKING_FLOW[shipment_status]):
                events.append(
                    {
                        "at": (placed_at + timedelta(days=step * 0.8)).isoformat(),
                        "status": label,
                        "location": rng.choice(hubs) if label != "Delivered"
                        else f"{order.shipping_city}, {order.shipping_pincode}",
                    }
                )

            db.add(
                Shipment(
                    order_id=order.id,
                    tracking_number=generate_tracking_number(rng.choice(CARRIERS)[:4]),
                    carrier=rng.choice(CARRIERS),
                    status=shipment_status,
                    current_location=events[-1]["location"],
                    estimated_delivery=order.expected_delivery,
                    delivered_at=order.delivered_at,
                    events=events,
                )
            )

        # An in-flight return on one delivered order, for the RMA demo.
        if status == OrderStatus.DELIVERED and days_ago == 6:
            item = order.items[0]
            db.add(
                ReturnRequest(
                    rma_number=generate_rma_number(),
                    order_id=order.id,
                    order_item_id=item.id,
                    customer_id=customer.id,
                    reason="Size did not fit",
                    status=ReturnStatus.PICKED_UP,
                    refund_amount=item.line_total,
                    pickup_scheduled_at=_now() - timedelta(days=1),
                )
            )

        if profile:
            profile.total_orders += 1
            profile.lifetime_value = round(profile.lifetime_value + order.total_amount, 2)

        orders.append(order)

    await db.flush()
    log.info("Seeded %d orders with shipments and returns.", len(orders))
    return orders


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------
async def seed_knowledge(db: AsyncSession) -> int:
    documents = []
    for article in KB_ARTICLES:
        doc = KBDocument(
            title=article["title"],
            slug=slugify(article["title"]),
            category=article["category"],
            content=article["content"].strip(),
            tags=article["tags"],
            view_count=rng.randint(40, 900),
            helpful_count=rng.randint(5, 200),
        )
        db.add(doc)
        documents.append(doc)
    await db.flush()

    total_chunks = 0
    for doc in documents:
        total_chunks += await rag.index_document(db, doc)
    await db.flush()

    log.info("Seeded %d KB articles -> %d embedded chunks.", len(documents), total_chunks)
    return total_chunks


# ---------------------------------------------------------------------------
# Historical conversations (so analytics is not an empty dashboard)
# ---------------------------------------------------------------------------
SCRIPTS: list[dict] = [
    {
        "intent": Intent.TRACK_SHIPMENT, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.NEUTRAL, "score": 0.0, "escalate": False, "csat": 5,
        "turns": [
            ("user", "Where is my order? It was supposed to arrive yesterday."),
            ("assistant", "Your parcel is **out for delivery** with BlueDart and the courier "
                          "expects to hand it over today before 19:00. Would you like me to "
                          "send you the live tracking link?"),
            ("user", "Yes please, thank you!"),
            ("assistant", "Sent to your registered number. Anything else I can help with?"),
        ],
        "tools": [("track_shipment", True, 42)],
    },
    {
        "intent": Intent.RETURN_REFUND, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.NEGATIVE, "score": -0.31, "escalate": False, "csat": 4,
        "turns": [
            ("user", "The shoes I ordered are too small, I want to return them."),
            ("assistant", "No problem at all - fashion items have a 14-day return window and "
                          "yours is well inside it. Shall I book a free pickup?"),
            ("user", "Yes do it."),
            ("assistant", "Done. RMA **RMA-8KD2L4XZ**, free pickup on Thursday, refund of "
                          "**₹3,299** within 48 hours of pickup. Anything else?"),
        ],
        "tools": [("search_knowledge_base", True, 18), ("initiate_return", True, 66)],
    },
    {
        "intent": Intent.DELIVERY_DELAY, "channel": ChannelType.VOICE,
        "sentiment": Sentiment.VERY_NEGATIVE, "score": -0.72, "escalate": True, "csat": 2,
        "turns": [
            ("user", "This is the third time I am calling. My order is nine days late and "
                     "nobody has bothered to call me back. This is absolutely unacceptable."),
            ("assistant", "You're right to be frustrated, and I'm sorry - nine days past the "
                          "promised date is not acceptable. I'm connecting you to a senior "
                          "colleague right now with your full history."),
        ],
        "tools": [("track_shipment", True, 51), ("escalate_to_human", True, 88)],
    },
    {
        "intent": Intent.STOCK_AVAILABILITY, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.POSITIVE, "score": 0.28, "escalate": False, "csat": 5,
        "turns": [
            ("user", "Do you have the AuraSound Buds Air 3 in stock?"),
            ("assistant", "Those are out of stock right now, but the **AuraSound Pro ANC "
                          "Headphones** are available at ₹8,999 and rated 4.5/5. "
                          "Want me to notify you when the Buds are back?"),
            ("user", "Yes, notify me. Thanks!"),
        ],
        "tools": [("check_product_availability", True, 29)],
    },
    {
        "intent": Intent.PAYMENT_ISSUE, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.NEGATIVE, "score": -0.44, "escalate": False, "csat": 4,
        "turns": [
            ("user", "I was charged twice for the same order."),
            ("assistant", "I can see one order and one duplicate authorisation. Duplicate "
                          "charges reverse automatically within 5-7 business days - yours was "
                          "initiated on the 12th, so it should land by the 19th. I've raised a "
                          "trace so it's tracked; ticket **TKT-250812-4KP2Z**."),
        ],
        "tools": [("search_knowledge_base", True, 21), ("create_support_ticket", True, 44)],
    },
    {
        "intent": Intent.CANCEL_ORDER, "channel": ChannelType.VOICE,
        "sentiment": Sentiment.NEUTRAL, "score": -0.05, "escalate": False, "csat": 5,
        "turns": [
            ("user", "I want to cancel my order please."),
            ("assistant", "I can cancel that for you - it hasn't shipped yet. That's the "
                          "mixer grinder at one thousand nine hundred rupees. Shall I go ahead?"),
            ("user", "Yes, cancel it."),
            ("assistant", "Cancelled. Your refund is on its way and takes three to five "
                          "business days. Anything else?"),
        ],
        "tools": [("lookup_order", True, 31), ("cancel_order", True, 73)],
    },
    {
        "intent": Intent.PRODUCT_RECOMMENDATION, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.POSITIVE, "score": 0.42, "escalate": False, "csat": 5,
        "turns": [
            ("user", "Looking for a good air purifier for a 400 sq ft bedroom."),
            ("assistant", "The **PureBreeze HEPA Air Purifier** covers 450 sq ft, runs at "
                          "24 dB in sleep mode and is ₹12,999 (rated 4.6/5). "
                          "Want me to check delivery to your pincode?"),
        ],
        "tools": [("recommend_products", True, 35)],
    },
    {
        "intent": Intent.HUMAN_HANDOFF, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.NEGATIVE, "score": -0.38, "escalate": True, "csat": 3,
        "turns": [
            ("user", "Just let me talk to a real person."),
            ("assistant", "Of course - connecting you now. Your reference is "
                          "**TKT-250814-9XQ1M** and I've passed on the whole conversation."),
        ],
        "tools": [("escalate_to_human", True, 79)],
    },
    {
        "intent": Intent.OFFERS_DISCOUNTS, "channel": ChannelType.WEB_CHAT,
        "sentiment": Sentiment.NEUTRAL, "score": 0.08, "escalate": False, "csat": 4,
        "turns": [
            ("user", "Any coupon I can use on a 3000 rupee order?"),
            ("assistant", "**FESTIVE500** needs ₹2,999 or more, so it applies - that's a flat "
                          "₹500 off. **WELCOME10** would only give you ₹300, so FESTIVE500 is "
                          "the better one."),
        ],
        "tools": [("search_knowledge_base", True, 16)],
    },
    {
        "intent": Intent.STORE_INFO, "channel": ChannelType.PHONE,
        "sentiment": Sentiment.NEUTRAL, "score": 0.05, "escalate": False, "csat": 5,
        "turns": [
            ("user", "What time does your Koramangala store close?"),
            ("assistant", "NovaMart Koramangala on 80 Feet Road is open until nine thirty "
                          "tonight, and they do click and collect."),
        ],
        "tools": [("find_nearby_store", True, 24)],
    },
    {
        "intent": Intent.ORDER_STATUS, "channel": ChannelType.WHATSAPP,
        "sentiment": Sentiment.NEUTRAL, "score": 0.0, "escalate": False, "csat": 4,
        "turns": [
            ("user", "status of ORD-2508123456"),
            ("assistant", "That order is **packed** and leaves our warehouse today. "
                          "Expected delivery is the 19th."),
        ],
        "tools": [("lookup_order", True, 27)],
    },
    {
        "intent": Intent.COMPLAINT, "channel": ChannelType.VOICE,
        "sentiment": Sentiment.VERY_NEGATIVE, "score": -0.81, "escalate": True, "csat": 2,
        "turns": [
            ("user", "The replacement you sent is damaged as well. This is pathetic service."),
            ("assistant", "That's a genuine failure on our side and I'm sorry. I'm escalating "
                          "this to a supervisor now - reference **TKT-250815-2LM8V** - and "
                          "they'll call you within two hours."),
        ],
        "tools": [("create_support_ticket", True, 47), ("escalate_to_human", True, 91)],
    },
]


async def seed_conversations(db: AsyncSession, users: dict[str, User]) -> int:
    customers = [u for u in users.values() if u.role == UserRole.CUSTOMER]
    agents = [u for u in users.values() if u.role in (UserRole.AGENT, UserRole.SUPERVISOR)]

    created = 0
    # Three passes over the scripts, spread across the last 14 days.
    for pass_index in range(3):
        for script_index, script in enumerate(SCRIPTS):
            days_ago = rng.randint(0, 13)
            started = _now() - timedelta(days=days_ago, hours=rng.randint(0, 22))
            customer = customers[(script_index + pass_index) % len(customers)]

            conversation = Conversation(
                customer_id=customer.id,
                channel=script["channel"],
                status=ConversationStatus.ESCALATED if script["escalate"]
                else ConversationStatus.RESOLVED,
                title=script["turns"][0][1][:70],
                primary_intent=script["intent"],
                last_sentiment=script["sentiment"],
                sentiment_score=script["score"],
                is_escalated=script["escalate"],
                escalated_at=started if script["escalate"] else None,
                escalation_reason=(
                    EscalationReason.NEGATIVE_SENTIMENT if script["score"] < -0.55
                    else EscalationReason.CUSTOMER_REQUEST
                ) if script["escalate"] else None,
                assigned_agent_id=rng.choice(agents).id if script["escalate"] else None,
                resolved_at=started + timedelta(minutes=rng.randint(2, 14)),
                resolved_by_ai=not script["escalate"],
                message_count=len(script["turns"]),
                total_tokens=rng.randint(900, 4200),
                total_latency_ms=rng.randint(1200, 5200),
                voice_seconds=(
                    rng.uniform(45, 260) if script["channel"] in
                    (ChannelType.VOICE, ChannelType.PHONE) else 0.0
                ),
            )
            conversation.created_at = started
            conversation.updated_at = started + timedelta(minutes=6)
            db.add(conversation)
            await db.flush()

            for turn_index, (role, content) in enumerate(script["turns"]):
                message = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.USER if role == "user" else MessageRole.ASSISTANT,
                    content=content,
                    intent=script["intent"],
                    intent_confidence=round(rng.uniform(0.62, 0.95), 3),
                    sentiment=script["sentiment"],
                    sentiment_score=script["score"],
                    latency_ms=rng.randint(700, 2600) if role == "assistant" else None,
                    tokens_in=rng.randint(200, 900) if role == "assistant" else None,
                    tokens_out=rng.randint(60, 320) if role == "assistant" else None,
                    model="claude-sonnet-5",
                )
                message.created_at = started + timedelta(seconds=turn_index * rng.randint(12, 55))
                db.add(message)

            for tool_name, success, duration in script["tools"]:
                db.add(
                    ToolCallLog(
                        conversation_id=conversation.id,
                        tool_name=tool_name,
                        arguments={"seeded": True},
                        result={"ok": success},
                        success=success,
                        duration_ms=duration + rng.randint(-8, 40),
                    )
                )

            if script["escalate"]:
                priority = (
                    TicketPriority.URGENT if script["score"] <= -0.7 else TicketPriority.HIGH
                )
                ticket = Ticket(
                    ticket_number=f"TKT-{started:%y%m%d}-{rng.randint(10000, 99999)}",
                    conversation_id=conversation.id,
                    customer_id=customer.id,
                    assigned_agent_id=conversation.assigned_agent_id,
                    subject=f"[Escalated] {script['turns'][0][1][:120]}",
                    description="Auto-escalated by the AI agent during a seeded conversation.",
                    category=script["intent"],
                    status=rng.choice(
                        [TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED]
                    ),
                    priority=priority,
                    created_by_agent=True,
                    sla_due_at=started + timedelta(hours=2 if priority == "urgent" else 8),
                    tags=["escalation", script["intent"], script["channel"]],
                )
                ticket.created_at = started
                db.add(ticket)

            db.add(
                Feedback(
                    conversation_id=conversation.id,
                    rating=script["csat"],
                    resolved=not script["escalate"],
                    nps=max(0, min(10, script["csat"] * 2)),
                    comment=None,
                )
            )
            created += 1

    await db.flush()
    log.info("Seeded %d historical conversations with tickets and CSAT.", created)
    return created


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
async def seed_all(db: AsyncSession) -> None:
    log.info("Seeding demo data ...")
    users = await seed_users(db)
    products = await seed_catalog(db)
    await seed_orders(db, users, products)
    await seed_knowledge(db)
    await seed_conversations(db, users)
    await db.commit()

    log.info("=" * 68)
    log.info("Demo accounts (all passwords below):")
    log.info("  admin      %-28s %s", settings.DEMO_ADMIN_EMAIL, settings.DEMO_ADMIN_PASSWORD)
    log.info("  supervisor %-28s %s", "supervisor@retailvoice.ai", DEMO_PASSWORD)
    log.info("  agent      %-28s %s", "agent1@retailvoice.ai", DEMO_PASSWORD)
    log.info("  customer   %-28s %s", "customer@retailvoice.ai", DEMO_PASSWORD)
    log.info("=" * 68)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed the RetailVoice demo database.")
    parser.add_argument("--reset", action="store_true", help="Drop every table first.")
    args = parser.parse_args()

    from app.db.init_db import create_tables, drop_tables

    if args.reset:
        await drop_tables()
    await create_tables()

    async with SessionLocal() as session:
        existing = (await session.execute(select(User).limit(1))).scalars().first()
        if existing and not args.reset:
            log.warning("Database already has users. Re-run with --reset to rebuild.")
            return
        await seed_all(session)


if __name__ == "__main__":
    asyncio.run(_main())
