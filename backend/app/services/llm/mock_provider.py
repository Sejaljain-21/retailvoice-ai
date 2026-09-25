"""Deterministic offline LLM provider.

This is what runs when no `ANTHROPIC_API_KEY` is configured. It is *not* a
language model - it is a rule-based planner that speaks the same tool-calling
protocol, so the whole product (agent loop, tool execution, RAG citations,
escalation, voice pipeline, analytics) is fully demonstrable and testable with
zero external dependencies or cost.

Swapping `LLM_PROVIDER=anthropic` replaces this class and nothing else.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.services.llm.base import (
    BaseLLMProvider,
    LLMResult,
    ToolSpec,
    ToolUse,
    last_user_text,
)

ORDER_RE = re.compile(r"\b(ORD[- ]?\d{4,}|#\s?\d{5,})\b", re.I)
TRACKING_RE = re.compile(r"\b([A-Z]{2,4}\d{8,})\b")


def _money(amount: Any, currency: str = "INR") -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, "")
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}{amount}"


def _pretty_status(status: str) -> str:
    return str(status).replace("_", " ").title()


class MockProvider(BaseLLMProvider):
    """Rule-based planner that emits tool calls and composes replies."""

    name = "mock"

    # Order matters: the first pattern that matches wins.
    ROUTES: list[tuple[str, str]] = [
        (r"\b(human|real person|agent|representative|supervisor|manager|escalat)\w*\b",
         "escalate_to_human"),
        # Policy questions must be grounded in the knowledge base, never in an
        # action tool - "what is your refund policy" is not a refund request.
        (r"\b(polic(y|ies)|terms|rules?|charges?|fees?|timeline|eligib\w+|warranty|"
         r"guarantee|how long|how many days|allowed to)\b",
         "search_knowledge_base"),
        (r"\b(otp|verification|verify|security code|one-time password)\b",
         "verify_security_otp"),
        (r"\b(cancel)\w*\b.*\b(order|purchase)\b|\bcancel my order\b", "cancel_order"),
        (r"\b(return|refund|replace|exchange|defect|damaged|broken|wrong item)\w*\b",
         "initiate_return"),
        (r"\b(track|tracking|where is|delivery status|shipment|courier|delayed|not arrived)\w*\b",
         "track_shipment"),
        (r"\b(order status|my order|order #|order number|ord-)\b", "lookup_order"),
        (r"\b(in stock|available|availability|do you have|stock)\b",
         "check_product_availability"),
        (r"\b(recommend|suggest|best|which one should|looking for|show me)\b",
         "recommend_products"),
        (r"\b(store|showroom|outlet|branch|nearby|near me|pickup)\b", "find_nearby_store"),
        (r"\b(my account|my profile|loyalty|points|tier|membership)\b", "get_customer_profile"),
        (r"\b(complaint|terrible|worst|awful|unacceptable|angry|furious|fed up)\b",
         "create_support_ticket"),
    ]

    GREETING_RE = re.compile(
        r"^\s*(hi|hey|hello|namaste|good (morning|afternoon|evening)|yo)\b", re.I
    )
    THANKS_RE = re.compile(r"\b(thanks|thank you|thx|appreciate)\b", re.I)
    BYE_RE = re.compile(r"\b(bye|goodbye|that'?s all|nothing else|see you)\b", re.I)

    # ------------------------------------------------------------------ API --
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        available = {t.name for t in (tools or [])}
        collected = self._collect_tool_results(messages)

        if collected:
            last_tool, last_res = collected[-1]
            if (
                last_tool == "verify_security_otp"
                and last_res.get("verified")
                and "cancel_order" in available
            ):
                order_num = last_res.get("order_number") or ""
                return LLMResult(
                    tool_uses=[
                        ToolUse(
                            id=f"toolu_{uuid.uuid4().hex[:16]}",
                            name="cancel_order",
                            input={
                                "order_number": order_num,
                                "reason": "Customer confirmed cancellation via verified security OTP",
                            },
                        )
                    ],
                    stop_reason="tool_use",
                    model="mock-planner-v1",
                    provider=self.name,
                )
            text = self._compose_answer(collected, last_user_text(messages))
            return self._result(text)

        utterance = last_user_text(messages)
        lowered = utterance.lower()

        # Pure social turns never need a tool.
        if self.GREETING_RE.search(lowered) and len(lowered.split()) <= 6:
            return self._result(
                "Hello! I'm Aura, your shopping assistant. I can check an order, "
                "track a delivery, start a return, or help you find a product. "
                "What can I do for you today?"
            )
        if self.BYE_RE.search(lowered):
            return self._result(
                "Happy to have helped. Have a great day, and do reach out any time!"
            )
        if self.THANKS_RE.search(lowered) and len(lowered.split()) <= 6:
            return self._result("You're very welcome! Anything else I can help with?")

        tool_name = self._route(lowered, available, messages)
        if tool_name:
            return LLMResult(
                tool_uses=[
                    ToolUse(
                        id=f"toolu_{uuid.uuid4().hex[:16]}",
                        name=tool_name,
                        input=self._build_args(tool_name, utterance),
                    )
                ],
                stop_reason="tool_use",
                model="mock-planner-v1",
                provider=self.name,
                tokens_in=len(system.split()) + len(utterance.split()),
                tokens_out=24,
            )

        # Default: consult the knowledge base rather than inventing an answer.
        if "search_knowledge_base" in available:
            return LLMResult(
                tool_uses=[
                    ToolUse(
                        id=f"toolu_{uuid.uuid4().hex[:16]}",
                        name="search_knowledge_base",
                        input={"query": utterance[:300]},
                    )
                ],
                stop_reason="tool_use",
                model="mock-planner-v1",
                provider=self.name,
            )

        return self._result(
            "I want to get this right for you. Could you share a little more detail - "
            "for example your order number, or the product you're asking about?"
        )

    # ------------------------------------------------------------- planning --
    def _route(self, lowered: str, available: set[str], messages: list[dict[str, Any]] | None = None) -> str | None:
        has_otp_verified = False
        if messages:
            msg_str = str(messages).lower()
            # After .lower(), Python bool True repr → 'true', so this check is correct
            if "verify_security_otp" in msg_str and ("authorization_granted" in msg_str or "'verified': true" in msg_str):
                has_otp_verified = True

        for pattern, tool in self.ROUTES:
            if tool in available and re.search(pattern, lowered, re.I):
                if tool == "cancel_order" and not has_otp_verified and "send_security_otp" in available:
                    return "send_security_otp"
                return tool
        if ORDER_RE.search(lowered) and "lookup_order" in available:
            return "lookup_order"
        return None

    def _build_args(self, tool: str, utterance: str) -> dict[str, Any]:
        order_match = ORDER_RE.search(utterance)
        order_ref = order_match.group(0).replace(" ", "").upper() if order_match else None

        match tool:
            case "send_security_otp":
                return {
                    "action": "cancel_order",
                    "order_number": order_ref or "",
                }
            case "verify_security_otp":
                digit_match = re.search(r"\b(\d{4})\b", utterance)
                code = digit_match.group(1) if digit_match else ""
                return {
                    "code": code,
                    "action": "cancel_order",
                    "order_number": order_ref or "",
                }
            case "lookup_order":
                return {"order_number": order_ref} if order_ref else {"most_recent": True}
            case "track_shipment":
                tracking = TRACKING_RE.search(utterance)
                if tracking:
                    return {"tracking_number": tracking.group(1)}
                return {"order_number": order_ref} if order_ref else {"most_recent": True}
            case "cancel_order":
                return {
                    "order_number": order_ref or "",
                    "reason": self._extract_reason(utterance) or "Customer requested cancellation",
                }
            case "initiate_return":
                return {
                    "order_number": order_ref or "",
                    "reason": self._extract_reason(utterance) or "Not as expected",
                    "comments": utterance[:400],
                }
            case "check_product_availability" | "recommend_products":
                return {"query": self._extract_product_query(utterance), "limit": 4}
            case "search_knowledge_base":
                return {"query": utterance[:300]}
            case "create_support_ticket":
                return {
                    "subject": utterance[:110].strip().capitalize() or "Customer complaint",
                    "description": utterance[:1500],
                    "priority": "high",
                }
            case "escalate_to_human":
                return {"reason": "customer_request", "summary": utterance[:400]}
            case "find_nearby_store":
                pin = re.search(r"\b\d{6}\b", utterance)
                city = self._extract_city(utterance)
                args: dict[str, Any] = {}
                if pin:
                    args["pincode"] = pin.group(0)
                if city:
                    args["city"] = city
                return args or {"city": ""}
            case _:
                return {}

    @staticmethod
    def _extract_reason(utterance: str) -> str | None:
        m = re.search(r"\b(?:because|since|as|due to)\s+(.{4,120})", utterance, re.I)
        if m:
            return m.group(1).strip().rstrip(".")
        for keyword, reason in (
            ("damaged", "Item arrived damaged"),
            ("defect", "Defective product"),
            ("wrong", "Wrong item delivered"),
            ("size", "Size did not fit"),
            ("late", "Delivery took too long"),
            ("duplicate", "Ordered by mistake / duplicate"),
        ):
            if keyword in utterance.lower():
                return reason
        return None

    @staticmethod
    def _extract_product_query(utterance: str) -> str:
        cleaned = re.sub(
            r"\b(do you have|is there|are there|in stock|available|availability|"
            r"can you|please|recommend|suggest|show me|looking for|i want|i need|"
            r"the|a|an|any|some|best)\b",
            " ",
            utterance,
            flags=re.I,
        )
        cleaned = re.sub(r"[^\w\s\-]", " ", cleaned)
        return " ".join(cleaned.split())[:120] or utterance[:120]

    @staticmethod
    def _extract_city(utterance: str) -> str | None:
        cities = [
            "mumbai", "delhi", "bengaluru", "bangalore", "hyderabad", "chennai",
            "kolkata", "pune", "ahmedabad", "jaipur", "lucknow", "noida", "gurugram",
        ]
        low = utterance.lower()
        for city in cities:
            if city in low:
                return city.title()
        return None

    # -------------------------------------------------------- result parsing --
    @staticmethod
    def _collect_tool_results(messages: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
        """Pair each tool_result with the name of the tool that produced it."""
        id_to_name: dict[str, str] = {}
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    id_to_name[block.get("id", "")] = block.get("name", "")

        results: list[tuple[str, dict[str, Any]]] = []
        # Only the trailing run of tool_result turns matters for this reply.
        for msg in reversed(messages):
            blocks = msg.get("content") or []
            if not isinstance(blocks, list):
                break
            found = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_result"]
            if not found:
                break
            for block in found:
                name = id_to_name.get(block.get("tool_use_id", ""), "unknown_tool")
                raw = block.get("content", "{}")
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    payload = {"raw": raw}
                results.insert(0, (name, payload if isinstance(payload, dict) else {"raw": payload}))
        return results

    # ------------------------------------------------------------ rendering --
    def _compose_answer(self, results: list[tuple[str, dict[str, Any]]], utterance: str) -> str:
        parts = [self._render(name, payload) for name, payload in results]
        body = "\n\n".join(p for p in parts if p)
        if not body:
            body = (
                "I looked into that but couldn't retrieve the details just now. "
                "Would you like me to connect you with a human colleague?"
            )
        return body

    def _render(self, tool: str, r: dict[str, Any]) -> str:  # noqa: C901 - a dispatch table
        match tool:
            case "lookup_order":
                if not r.get("found"):
                    return (
                        r.get("message")
                        or "I couldn't find that order. Could you double-check the order number?"
                    )
                o = r.get("order", {})
                items = ", ".join(
                    f"{i.get('quantity', 1)} x {i.get('name')}" for i in o.get("items", [])[:4]
                )
                lines = [
                    f"Order **{o.get('order_number')}** is currently "
                    f"**{_pretty_status(o.get('status'))}**.",
                    f"- Items: {items}" if items else "",
                    f"- Order total: {_money(o.get('total_amount'), o.get('currency', 'INR'))} "
                    f"({_pretty_status(o.get('payment_status', ''))})",
                ]
                if o.get("expected_delivery"):
                    lines.append(f"- Expected delivery: {o['expected_delivery'][:10]}")
                if o.get("tracking_number"):
                    lines.append(f"- Tracking number: {o['tracking_number']}")
                lines.append("\nWould you like tracking details or help with anything else?")
                return "\n".join(x for x in lines if x)

            case "track_shipment":
                if not r.get("found"):
                    return r.get("message") or (
                        "I couldn't find a shipment for that order yet. It is likely still being "
                        "packed - you'll get tracking details by SMS and email once it ships."
                    )
                lines = [
                    f"Your parcel is **{_pretty_status(r.get('status'))}** with "
                    f"{r.get('carrier')} (tracking {r.get('tracking_number')})."
                ]
                if r.get("current_location"):
                    lines.append(f"- Last scanned at: {r['current_location']}")
                if r.get("estimated_delivery"):
                    lines.append(f"- Estimated delivery: {r['estimated_delivery'][:10]}")
                events = r.get("events") or []
                if events:
                    latest = events[-1]
                    lines.append(
                        f"- Latest update: {latest.get('status')} - {latest.get('location', '')}"
                    )
                if r.get("is_delayed"):
                    lines.append(
                        "\nI can see this is running behind the promised date, and I'm sorry about "
                        "that. I can raise a delay complaint or arrange a goodwill voucher - "
                        "just say the word."
                    )
                return "\n".join(lines)

            case "send_security_otp":
                phone = r.get("masked_phone", "your registered phone")
                order_num = r.get("order_number") or ""
                order_bold = f" for order **{order_num}**" if order_num else ""
                return (
                    f"For your security, I have dispatched a live 4-digit verification code to your registered "
                    f"mobile number ({phone}){order_bold}.\n\n"
                    "Please check your SMS and enter or speak the 4-digit code to authorize cancelling this order."
                )

            case "verify_security_otp":
                if r.get("verified"):
                    order = r.get("order_number") or ""
                    order_bold = f" for order **{order}**" if order else ""
                    return (
                        f"✓ Security authorization code **{r.get('code', '')}** verified successfully!\n\n"
                        f"Your identity has been confirmed via live SMS authentication. "
                        f"Proceeding to cancel the order{order_bold} and initiate your full refund..."
                    )
                return r.get("message") or "The verification code did not match. Please re-check the 4-digit SMS code."

            case "cancel_order":
                if r.get("success"):
                    return (
                        f"Done - order **{r.get('order_number')}** has been cancelled.\n\n"
                        f"A refund of {_money(r.get('refund_amount'))} will reach your original "
                        "payment method in 3-5 business days. "
                        "You'll receive a confirmation email shortly."
                    )
                if r.get("requires_otp"):
                    phone = r.get("masked_phone", "your registered mobile")
                    order = r.get("order_number") or ""
                    return (
                        f"For your security, cancelling order **{order}** requires SMS verification.\n\n"
                        f"I have dispatched a 4-digit code to your registered mobile number ({phone}). "
                        "Please check your SMS and enter or speak the code to authorize this transaction."
                    )
                return r.get("message") or (
                    "That order can no longer be cancelled because it has already shipped. "
                    "You can refuse delivery, or I can start a return once it arrives - "
                    "which would you prefer?"
                )

            case "initiate_return":
                if r.get("success"):
                    msg = [
                        f"Your return is confirmed. RMA number **{r.get('rma_number')}**.",
                        f"- Refund amount: {_money(r.get('refund_amount'))}",
                        f"- Refund method: "
                        f"{_pretty_status(r.get('refund_method', 'original_payment_method'))}",
                    ]
                    if r.get("pickup_scheduled_at"):
                        msg.append(f"- Free pickup scheduled for {r['pickup_scheduled_at'][:10]}")
                    msg.append(
                        "\nPlease keep the item in its original packaging. "
                        "The refund is processed within 48 hours of pickup."
                    )
                    return "\n".join(msg)
                return r.get("message") or (
                    "I wasn't able to start the return automatically. Let me get a colleague "
                    "to review this for you."
                )

            case "check_product_availability" | "recommend_products":
                products = r.get("products") or []
                if not products:
                    return (
                        "I couldn't find a match for that in our catalogue right now. "
                        "Could you tell me the brand or model you have in mind?"
                    )
                header = (
                    "Here's what I found:"
                    if tool == "check_product_availability"
                    else "Based on what you described, these look like a good fit:"
                )
                lines = [header]
                for p in products[:4]:
                    stock = (
                        f"in stock ({p.get('stock_quantity')} left)"
                        if p.get("in_stock")
                        else "currently out of stock"
                    )
                    lines.append(
                        f"- **{p.get('name')}** by {p.get('brand')} - "
                        f"{_money(p.get('price'), p.get('currency', 'INR'))}, "
                        f"rated {p.get('rating')}/5, {stock}"
                    )
                lines.append("\nWant me to check delivery time to your pincode for any of these?")
                return "\n".join(lines)

            case "search_knowledge_base":
                hits = r.get("hits") or []
                if not hits:
                    return (
                        "I don't have a documented answer for that. Rather than guess, let me "
                        "create a ticket so a specialist can respond - shall I go ahead?"
                    )
                top = hits[0]
                lines = [
                    f"Here's what our help centre says under **{top.get('title')}**:",
                    "",
                    self._clean_passage(top.get("snippet", "")),
                ]
                # Several passages can come from the same article; only list
                # each article once, and never the one already quoted above.
                related: list[str] = []
                for hit in hits[1:]:
                    title = str(hit.get("title", ""))
                    if title and title != top.get("title") and title not in related:
                        related.append(title)
                if related:
                    lines.append(
                        "\nRelated articles: " + ", ".join(f"*{t}*" for t in related[:2])
                    )
                lines.append("\nDoes that answer your question?")
                return "\n".join(lines)

            case "get_customer_profile":
                if not r.get("found"):
                    return (
                        "I'll need you to sign in before I can pull up your account details. "
                        "Once you're logged in I can see your orders instantly."
                    )
                lines = [
                    f"Here's your account summary, {r.get('name', 'there')}:",
                    f"- Membership tier: **{_pretty_status(r.get('tier', 'standard'))}**",
                    f"- Loyalty points: {r.get('loyalty_points', 0)}",
                    f"- Orders placed: {r.get('total_orders', 0)}",
                ]
                recent = r.get("recent_orders") or []
                if recent:
                    lines.append("- Recent orders:")
                    for o in recent[:3]:
                        lines.append(
                            f"    - {o.get('order_number')} - {_pretty_status(o.get('status'))}, "
                            f"{_money(o.get('total_amount'))}"
                        )
                return "\n".join(lines)

            case "create_support_ticket":
                return (
                    f"I've logged this as ticket **{r.get('ticket_number')}** with "
                    f"**{_pretty_status(r.get('priority', 'medium'))}** priority. "
                    f"Our team responds within {r.get('sla_hours', 24)} hours, and you'll get "
                    "updates by email. I'm sorry for the trouble this has caused."
                )

            case "escalate_to_human":
                return (
                    "Of course - I'm connecting you to a human colleague now. "
                    f"Your reference is **{r.get('ticket_number')}** and you're "
                    f"number {r.get('queue_position', 1)} in the queue. "
                    "I've shared the full conversation so you won't need to repeat yourself."
                )

            case "apply_goodwill_coupon":
                if r.get("success"):
                    return (
                        f"I've added a goodwill voucher to your account: **{r.get('code')}** "
                        f"worth {_money(r.get('value'))}, valid until {str(r.get('expires_at'))[:10]}. "
                        "Thank you for your patience."
                    )
                return r.get("message") or "I couldn't issue a voucher on this account."

            case "find_nearby_store":
                stores = r.get("stores") or []
                if not stores:
                    return (
                        "I couldn't find a store in that area. We deliver to every serviceable "
                        "pincode though - would you like me to check delivery instead?"
                    )
                lines = ["Here are the closest stores:"]
                for s in stores[:3]:
                    lines.append(
                        f"- **{s.get('name')}**, {s.get('address')} "
                        f"(open {s.get('opening_hours')}) - {s.get('phone', 'n/a')}"
                    )
                return "\n".join(lines)

            case _:
                return json.dumps(r)[:600]

    # --------------------------------------------------------------- helpers --
    @staticmethod
    def _clean_passage(snippet: str, limit: int = 700) -> str:
        """Trim a retrieved chunk to whole sentences so the reply never starts or
        ends mid-thought. A real LLM paraphrases instead; this keeps the offline
        answer readable and, more importantly, faithful to the source."""
        text = " ".join(snippet.split()) if snippet else ""
        if not text:
            return ""
        # Drop a leading fragment left over from chunk overlap.
        if text and text[0].islower():
            first_stop = re.search(r"[.!?]\s+", text)
            if first_stop and first_stop.end() < len(text) - 40:
                text = text[first_stop.end():]
        if len(text) <= limit:
            return text
        cut = text[:limit]
        last_stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        return (cut[:last_stop + 1] if last_stop > 120 else cut.rstrip() + " ...")

    def _result(self, text: str) -> LLMResult:
        return LLMResult(
            text=text,
            stop_reason="end_turn",
            model="mock-planner-v1",
            provider=self.name,
            tokens_out=len(text.split()),
        )
