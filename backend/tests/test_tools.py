"""Direct tests of the agent's tool handlers, bypassing the LLM."""

from __future__ import annotations

from sqlalchemy import select

from app.agent.tools import ToolContext, execute, tool_names, tool_schemas
from app.models.enums import ChannelType, OrderStatus
from app.models.support import Conversation
from app.models.user import User
from app.services import orders_service as orders


async def _context(db, email: str = "customer@retailvoice.ai") -> ToolContext:
    user = (await db.execute(select(User).where(User.email == email))).scalars().first()
    conversation = Conversation(customer_id=user.id, channel=ChannelType.WEB_CHAT)
    db.add(conversation)
    await db.flush()
    return ToolContext(db=db, conversation=conversation, user=user)


# ------------------------------------------------------------------ schema --
def test_every_tool_has_a_valid_schema() -> None:
    schemas = tool_schemas()
    assert len(schemas) >= 12
    for schema in schemas:
        assert schema["name"] and len(schema["description"]) > 40
        assert schema["input_schema"]["type"] == "object"
        for name, spec in schema["input_schema"]["properties"].items():
            assert "description" in spec, f"{schema['name']}.{name} has no description"
        for required in schema["input_schema"]["required"]:
            assert required in schema["input_schema"]["properties"]


def test_tool_names_are_unique() -> None:
    assert len(tool_names()) == len(set(tool_names()))


# ------------------------------------------------------------------- order --
async def test_lookup_most_recent_order(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "lookup_order", {"most_recent": True})
    assert result["found"] is True
    assert result["order"]["order_number"].startswith("ORD-")
    assert result["order"]["items"]


async def test_lookup_unknown_order_is_customer_safe(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "lookup_order", {"order_number": "ORD-0000000000"})
    assert result["found"] is False
    # The customer-visible message must not contain internal instructions.
    assert "Ask the customer" not in result["message"]
    assert "agent_hint" in result


async def test_customer_cannot_read_another_customers_order(db) -> None:
    other = await _context(db, "meera.nair@example.com")
    their_order = (await execute(other, "lookup_order", {"most_recent": True}))["order"]

    mine = await _context(db)
    result = await execute(
        mine, "lookup_order", {"order_number": their_order["order_number"]}
    )
    assert result["found"] is False
    assert result.get("authorization_failed") is True


async def test_track_shipment_flags_a_late_parcel(db) -> None:
    ctx = await _context(db)
    late = (
        await orders.list_orders(db, customer_id=ctx.user.id, status=OrderStatus.SHIPPED)
    )
    if not late:
        return
    result = await execute(
        ctx, "track_shipment", {"order_number": late[0].order_number}
    )
    assert result["found"] is True
    assert "is_delayed" in result


async def test_cancel_refuses_a_delivered_order(db) -> None:
    ctx = await _context(db)
    delivered = await orders.latest_order_for(
        db, ctx.user.id, [OrderStatus.DELIVERED]
    )
    if delivered is None:
        return
    result = await execute(
        ctx, "cancel_order",
        {"order_number": delivered.order_number, "reason": "changed my mind"},
    )
    assert result["success"] is False
    assert "cancel" in result["message"].lower()


# --------------------------------------------------------------- catalogue --
async def test_product_availability(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "check_product_availability", {"query": "headphones"})
    assert result["count"] >= 1
    assert "in_stock" in result["products"][0]


async def test_recommendations_only_return_stocked_items(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "recommend_products", {"query": "air purifier"})
    assert all(p["in_stock"] for p in result["products"])


async def test_delivery_estimate_validates_the_pincode(db) -> None:
    ctx = await _context(db)
    assert (await execute(ctx, "check_delivery_estimate", {"pincode": "12"}))[
        "serviceable"
    ] is False
    good = await execute(ctx, "check_delivery_estimate", {"pincode": "560095"})
    assert good["estimated_days"] >= 1


async def test_find_nearby_store(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "find_nearby_store", {"city": "Mumbai"})
    assert result["count"] >= 1
    assert result["stores"][0]["city"] == "Mumbai"


# --------------------------------------------------------------- knowledge --
async def test_knowledge_search_records_citations(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "search_knowledge_base", {"query": "return window"})
    assert result["count"] >= 1
    assert ctx.flags["citations"], "citations must be captured for the reply"


async def test_customer_profile(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "get_customer_profile", {})
    assert result["found"] is True
    assert result["tier"] == "gold"


async def test_profile_requires_sign_in(db) -> None:
    conversation = Conversation(channel=ChannelType.WEB_CHAT)
    db.add(conversation)
    await db.flush()
    ctx = ToolContext(db=db, conversation=conversation, user=None)

    result = await execute(ctx, "get_customer_profile", {})
    assert result["needs_authentication"] is True


# --------------------------------------------------------- service recovery --
async def test_goodwill_coupon_respects_the_policy_limit(db) -> None:
    ctx = await _context(db)
    refused = await execute(
        ctx, "apply_goodwill_coupon", {"reason": "late delivery", "amount": 50000}
    )
    assert refused["success"] is False
    assert ctx.flags.get("policy_blocked") is True

    allowed = await execute(
        ctx, "apply_goodwill_coupon", {"reason": "late delivery", "amount": 200}
    )
    assert allowed["success"] is True
    assert allowed["code"].startswith("SORRY")


async def test_escalation_creates_a_ticket_and_flags_the_conversation(db) -> None:
    ctx = await _context(db)
    result = await execute(
        ctx, "escalate_to_human",
        {"reason": "customer_request", "summary": "Wants a human"},
    )
    assert result["escalated"] is True
    assert result["ticket_number"].startswith("TKT-")
    assert ctx.conversation.is_escalated is True


# ------------------------------------------------------------- error paths --
async def test_unknown_tool_returns_data_not_an_exception(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "definitely_not_a_tool", {})
    assert "error" in result
    assert "available" in result


async def test_bad_arguments_are_reported_as_data(db) -> None:
    ctx = await _context(db)
    result = await execute(ctx, "find_nearby_store", {"nonexistent_argument": 1})
    assert "error" in result
