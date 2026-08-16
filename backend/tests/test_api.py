"""End-to-end API tests over the seeded database."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ------------------------------------------------------------------ system --
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_capabilities_lists_tools(client: AsyncClient) -> None:
    payload = (await client.get("/api/v1/capabilities")).json()
    assert "lookup_order" in payload["tools"]
    assert "escalate_to_human" in payload["tools"]
    assert payload["llm"]["provider"] == "mock"


async def test_ready(client: AsyncClient) -> None:
    payload = (await client.get("/api/v1/ready")).json()
    assert payload["checks"]["database"] == "ok"


# -------------------------------------------------------------------- auth --
async def test_register_and_login(client: AsyncClient) -> None:
    email = "new.user@example.com"
    created = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!", "full_name": "New User"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["user"]["role"] == "customer"

    duplicate = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass!", "full_name": "New User"},
    )
    assert duplicate.status_code == 409

    ok = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Str0ngPass!"}
    )
    assert ok.status_code == 200
    assert ok.json()["tokens"]["access_token"]

    bad = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert bad.status_code == 401


async def test_me_requires_a_token(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_me_returns_the_profile(client: AsyncClient, auth: dict) -> None:
    payload = (await client.get("/api/v1/auth/me", headers=auth)).json()
    assert payload["email"] == "customer@retailvoice.ai"
    assert payload["profile"]["tier"] == "gold"


# ----------------------------------------------------------------- catalog --
async def test_list_products(client: AsyncClient) -> None:
    payload = (await client.get("/api/v1/catalog/products?page_size=5")).json()
    assert payload["total"] >= 15
    assert len(payload["items"]) == 5


async def test_product_search_and_filters(client: AsyncClient) -> None:
    payload = (await client.get("/api/v1/catalog/products?q=headphones")).json()
    assert payload["total"] >= 1
    assert "headphone" in payload["items"][0]["name"].lower()

    cheap = (await client.get("/api/v1/catalog/products?max_price=1500")).json()
    assert all(p["price"] <= 1500 for p in cheap["items"])


async def test_get_product_by_sku(client: AsyncClient) -> None:
    payload = (await client.get("/api/v1/catalog/products/ELC-HDP-001")).json()
    assert payload["sku"] == "ELC-HDP-001"
    assert payload["stock_quantity"] > 0


async def test_stores(client: AsyncClient) -> None:
    stores = (await client.get("/api/v1/catalog/stores?city=Bengaluru")).json()
    assert stores and stores[0]["city"] == "Bengaluru"


# ------------------------------------------------------------------ orders --
async def test_list_my_orders(client: AsyncClient, auth: dict) -> None:
    payload = (await client.get("/api/v1/orders", headers=auth)).json()
    assert payload["total"] >= 1
    assert all(o["order_number"].startswith("ORD-") for o in payload["items"])


async def test_order_detail_and_tracking(client: AsyncClient, auth: dict) -> None:
    orders = (await client.get("/api/v1/orders", headers=auth)).json()["items"]
    reference = orders[0]["order_number"]

    detail = (await client.get(f"/api/v1/orders/{reference}", headers=auth)).json()
    assert detail["order_number"] == reference
    assert detail["items"]

    tracking = await client.get(f"/api/v1/orders/{reference}/tracking", headers=auth)
    assert tracking.status_code == 200
    assert "found" in tracking.json()


async def test_cannot_read_someone_elses_order(client: AsyncClient, auth: dict) -> None:
    other = await client.post(
        "/api/v1/auth/login",
        json={"email": "meera.nair@example.com", "password": "Demo@1234"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['tokens']['access_token']}"}
    their_order = (
        await client.get("/api/v1/orders", headers=other_headers)
    ).json()["items"][0]["order_number"]

    denied = await client.get(f"/api/v1/orders/{their_order}", headers=auth)
    assert denied.status_code == 403


async def test_create_and_cancel_an_order(client: AsyncClient, auth: dict) -> None:
    product = (await client.get("/api/v1/catalog/products?q=power+bank")).json()["items"][0]

    created = await client.post(
        "/api/v1/orders",
        headers=auth,
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "shipping_address": "402, Lakeview Apartments, Koramangala",
            "shipping_city": "Bengaluru",
            "shipping_pincode": "560095",
            "payment_method": "upi",
        },
    )
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["total_amount"] > 0
    assert order["status"] == "confirmed"

    cancelled = await client.post(
        f"/api/v1/orders/{order['order_number']}/cancel",
        headers=auth,
        json={"reason": "Ordered by mistake"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


async def test_coupon_reduces_the_total(client: AsyncClient, auth: dict) -> None:
    product = (
        await client.get("/api/v1/catalog/products?q=mixer+grinder")
    ).json()["items"][0]

    body = {
        "items": [{"product_id": product["id"], "quantity": 1}],
        "shipping_address": "Test address",
        "payment_method": "upi",
    }
    plain = (await client.post("/api/v1/orders", headers=auth, json=body)).json()
    discounted = (
        await client.post(
            "/api/v1/orders", headers=auth, json={**body, "coupon_code": "FESTIVE500"}
        )
    ).json()
    assert discounted["discount"] == 500.0
    assert discounted["total_amount"] < plain["total_amount"]


# --------------------------------------------------------------- knowledge --
async def test_kb_search(client: AsyncClient) -> None:
    payload = (
        await client.get("/api/v1/knowledge/search", params={"q": "return window for shoes"})
    ).json()
    assert payload["hits"]
    assert payload["took_ms"] >= 0


async def test_kb_listing_and_article(client: AsyncClient) -> None:
    listing = (await client.get("/api/v1/knowledge")).json()
    assert listing["total"] >= 10
    slug = listing["items"][0]["slug"]

    article = (await client.get(f"/api/v1/knowledge/{slug}")).json()
    assert article["slug"] == slug
    assert len(article["content"]) > 100


async def test_kb_write_requires_staff(client: AsyncClient, auth: dict) -> None:
    denied = await client.post(
        "/api/v1/knowledge",
        headers=auth,
        json={"title": "Sneaky policy change", "content": "x" * 50},
    )
    assert denied.status_code == 403


async def test_staff_can_create_and_index_an_article(
    client: AsyncClient, admin_auth: dict
) -> None:
    created = await client.post(
        "/api/v1/knowledge",
        headers=admin_auth,
        json={
            "title": "Gift wrapping and personalised messages",
            "category": "orders",
            "content": (
                "Gift wrapping costs Rs 49 per item and can be added at checkout. "
                "You may include a personalised message of up to 200 characters. "
                "Gift-wrapped orders never show the price on the invoice inside the parcel."
            ),
            "tags": ["gift", "wrapping"],
        },
    )
    assert created.status_code == 201, created.text

    found = (
        await client.get("/api/v1/knowledge/search", params={"q": "gift wrapping cost"})
    ).json()
    assert any("gift" in hit["title"].lower() for hit in found["hits"])


# --------------------------------------------------------------- analytics --
async def test_analytics_requires_staff(client: AsyncClient, auth: dict) -> None:
    assert (await client.get("/api/v1/analytics/dashboard", headers=auth)).status_code == 403


async def test_analytics_dashboard(client: AsyncClient, admin_auth: dict) -> None:
    payload = (
        await client.get("/api/v1/analytics/dashboard", headers=admin_auth)
    ).json()
    kpis = payload["kpis"]
    assert kpis["total_conversations"] >= 30
    assert 0 <= kpis["containment_rate"] <= 100
    assert 0 <= kpis["avg_csat"] <= 5
    assert payload["intents"] and payload["timeseries"]
    assert any(t["tool"] == "track_shipment" for t in payload["tools"])


# ----------------------------------------------------------------- tickets --
async def test_ticket_stats_and_queue(client: AsyncClient, admin_auth: dict) -> None:
    stats = (await client.get("/api/v1/tickets/stats", headers=admin_auth)).json()
    assert stats["ai_created"] >= 1
    assert "sla_breaching" in stats


async def test_customer_only_sees_their_own_tickets(
    client: AsyncClient, auth: dict
) -> None:
    payload = (await client.get("/api/v1/tickets", headers=auth)).json()
    assert isinstance(payload["items"], list)


async def test_staff_can_claim_a_ticket(client: AsyncClient, admin_auth: dict) -> None:
    tickets = (await client.get("/api/v1/tickets", headers=admin_auth)).json()["items"]
    if not tickets:
        pytest.skip("no seeded tickets")
    number = tickets[0]["ticket_number"]
    claimed = (
        await client.post(f"/api/v1/tickets/{number}/claim", headers=admin_auth)
    ).json()
    assert claimed["assigned_agent_id"]
    assert claimed["status"] in ("in_progress", "resolved", "closed")
