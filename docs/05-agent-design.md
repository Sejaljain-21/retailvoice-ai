# 5 · Agent design

---

## 5.1 The loop

```python
for iteration in range(AGENT_MAX_TOOL_ITERATIONS):        # default 6
    result = await llm.complete(system=prompt, messages=messages, tools=specs)
    if not result.wants_tools:
        reply_text = result.text
        break

    messages.append(assistant_turn(result))               # text + tool_use blocks
    for call in result.tool_uses:
        payload = await execute_tool(ctx, call.name, call.input)
        log_to_database(call, payload, duration)
        tool_results.append(tool_result_block(call.id, payload))
    messages.append({"role": "user", "content": tool_results})
else:
    # Ceiling reached — stop rather than loop, and hand to a human.
    reply_text = "This is taking me longer than it should…"
    ctx.flags["force_escalate"] = True
```

The `else` branch matters. An agent that loops forever is worse than one that gives up:
it burns tokens, leaves the customer waiting, and usually indicates a genuine problem.
Hitting the ceiling is treated as a failure signal and escalates.

---

## 5.2 Prompt construction

The system prompt is assembled per turn from four parts, so each is independently
testable and the voice channel swaps only the style section.

```
┌─ PERSONA ───────────────────────────────────────────────┐
│ Aura, AI support agent for NovaMart. Warm, efficient,   │
│ takes ownership, never blames the customer.             │
├─ OPERATING RULES (9) ───────────────────────────────────┤
│ 1 Ground every factual claim in a tool result           │
│ 2 Policy questions go through search_knowledge_base     │
│ 3 Confirm before destructive actions                    │
│ 4 One question at a time                                │
│ 5 Escalate rather than struggle                         │
│ 6 Acknowledge feelings before facts                     │
│ 7 Never invent identifiers, timelines or policy         │
│ 8 Never ask for CVV / OTP / PIN / password              │
│ 9 Match the customer's language                         │
├─ CHANNEL MODIFIER ──────────────────────────────────────┤
│ chat:  markdown, bold key values, < 120 words           │
│ voice: < 55 words, no markdown, speakable identifiers,  │
│        one question then stop                           │
├─ LIVE CONTEXT ──────────────────────────────────────────┤
│ timestamp · channel · turn count                        │
│ detected intent and sentiment this turn                 │
│ customer name, tier, points, city (or "not signed in")  │
│ open ticket count — is this a follow-up?                │
│ WARNING line when sentiment ≤ −0.55                     │
│ high-value-customer note for gold/platinum              │
├─ PRE-FETCHED PASSAGES (conditional) ────────────────────┤
│ Top-3 help-centre passages, when the intent suggests    │
│ a policy question                                       │
└─────────────────────────────────────────────────────────┘
```

Two details worth calling out:

**Live context is regenerated every turn**, not once per conversation. Sentiment moves,
and the prompt must move with it — the WARNING line appearing mid-conversation is often
what changes the model's tone before the escalation rule fires.

**Passages are pre-fetched, not just tool-fetched.** For intents that are usually policy
questions, retrieval runs *before* the model is called and the results are injected into
the prompt. This removes a round-trip on the most common question type. The model can
still call `search_knowledge_base` itself when the pre-fetch missed.

---

## 5.3 The 13 tools

### Orders

| Tool | Purpose | Guard |
|---|---|---|
| `lookup_order` | Full status: items, totals, payment, ETA, tracking | Ownership |
| `track_shipment` | Carrier, last scan, ETA, scan history, `is_delayed` | Ownership |
| `cancel_order` | Cancel, restock, refund | Ownership + `is_cancellable` |
| `initiate_return` | RMA, refund amount, booked pickup | Ownership + window + returnability |
| `get_order_history` | Recent orders when the number is forgotten | Requires sign-in |

### Catalogue

| Tool | Purpose |
|---|---|
| `check_product_availability` | Live stock, price, rating |
| `recommend_products` | Ranked, in-stock only, honours a budget |
| `check_delivery_estimate` | Days, fee, same-day and COD availability by pincode |
| `find_nearby_store` | Address, phone, hours, click-and-collect |

### Knowledge and account

| Tool | Purpose |
|---|---|
| `search_knowledge_base` | Hybrid retrieval; **the only sanctioned source of policy** |
| `get_customer_profile` | Tier, points, lifetime orders, recent orders |

### Service recovery

| Tool | Purpose | Guard |
|---|---|---|
| `create_support_ticket` | Log something needing back-office work | — |
| `escalate_to_human` | Hand over with transcript, assign least-loaded agent | — |
| `apply_goodwill_coupon` | Issue a voucher for a genuine service failure | ≤ ₹500 policy limit |

### Anatomy of a tool

```python
@tool(
    "cancel_order",
    "Cancel an order that has not shipped yet and start the refund. Only call "
    "this after the customer has clearly confirmed…",
    _obj({"order_number": _str("Order reference to cancel."),
           "reason": _str("Why the customer wants to cancel.")}, ["order_number", "reason"]),
)
async def cancel_order(ctx, order_number="", reason="Customer request"):
    order, error = await _resolve_order(ctx, order_number, not order_number,
                                        orders.CANCELLABLE_STATUSES)
    if error:
        return error
    result = await orders.cancel_order(ctx.db, order, reason)
    if result.get("success"):
        ctx.flags["order_cancelled"] = order.order_number
    return result
```

Three principles are visible here:

1. **The description is the interface.** It tells the model *when* to call the tool and
   *when not to* — "only after the customer has clearly confirmed" does more work than
   any amount of prompt text elsewhere.
2. **Guards are in the handler, not the prompt.** Ownership and cancellability are
   checked in code. A model that hallucinates someone else's order number still gets
   refused.
3. **Errors are data.** The handler returns a dict; it never raises into the loop.

### Customer-safe messages

Every failure path returns two fields:

```python
{
  "found": False,
  "message":    "Which order is this about? Your order number looks like ORD-2508123456.",
  "agent_hint": "Ask the customer for the order number, then call the tool again.",
}
```

`message` is safe to say out loud; `agent_hint` is the internal instruction. This split
exists because it was a real defect: an early version returned *"Ask the customer to
re-read the order number"* as the only field, and the weaker offline planner echoed that
instruction verbatim to the customer.

### Smart fallbacks

When no order number is given, `cancel_order` and `initiate_return` resolve to the
customer's most recent order **that the action is actually valid for** —
`CANCELLABLE_STATUSES` for one, `RETURNABLE_STATUSES` for the other. "Cancel my order"
therefore works without an interrogation, and if nothing is cancellable the customer
gets a useful sentence rather than a request for a number that would not have helped.

---

## 5.4 Guardrails

### Input

| Check | Patterns | Action |
|---|---|---|
| Prompt injection | "ignore previous instructions", "reveal your system prompt", "developer mode" | Log a warning |
| Legal threat | lawyer, consumer court, sue, police, FIR | **Force escalation** |
| Fraud | unauthorised transaction, stolen card, hacked | **Force escalation** |
| Safety / injury | injured, burn, shock, fire, exploded, hospital, allergic | **Force escalation** |
| Welfare | self-harm, suicide | **Force escalation** |
| Reputational | media/press/viral + complain/expose | **Force escalation** |
| Credentials | CVV, OTP, UPI PIN, password | Flag |

The forced-escalation categories are not judgement calls. A support bot must not attempt
to handle a product-injury claim or a fraud report, regardless of how confident it is.

### Output

| Check | Action |
|---|---|
| `sk-ant-…`, `sk-…`, bearer tokens, `postgres://` DSNs | Redact |
| "as an AI language model", "my system prompt" | Flag |
| Empty response | Replace with the fallback message |

---

## 5.5 Escalation policy

```python
def should_escalate(nlu, turn_count, tool_errors, customer_tier, ...):
    if guardrail.forced_escalation:                      → POLICY_LIMIT
    if intent == HUMAN_HANDOFF and confidence ≥ 0.5:     → CUSTOMER_REQUEST
    if sentiment_score ≤ −0.55:                          → NEGATIVE_SENTIMENT
    if tool_errors ≥ 2:                                  → TOOL_ERROR
    if consecutive_low_confidence ≥ 3:                   → LOW_CONFIDENCE
    if turn_count ≥ 8 and sentiment < 0:                 → REPEATED_FAILURE
    if tier in (gold, platinum) and negative
       and turn_count ≥ 4:                               → HIGH_VALUE_CUSTOMER
    return no
```

**This runs after the model has produced its reply and can override it.** The model does
not get a vote. If a customer is clearly upset, a human is assigned whether or not the
LLM decided to call `escalate_to_human`.

On escalation the system:

1. Flags the conversation and stamps the reason.
2. Derives priority from intent + sentiment + tier.
3. Builds a ticket whose description contains the **full transcript**, so the customer
   never repeats themselves.
4. Assigns the least-loaded active agent.
5. Appends a handoff sentence with the reference number to the reply.

**Priority derivation**

| Signal | Points |
|---|---|
| Intent ∈ {complaint, payment issue, delivery delay, handoff} | +2 |
| Sentiment ≤ −0.55 | +2 |
| Sentiment ≤ −0.20 | +1 |
| Tier ∈ {gold, platinum} | +1 |

≥ 4 urgent (2 h SLA) · ≥ 2 high (8 h) · ≥ 1 medium (24 h) · else low (72 h).

---

## 5.6 Grounding in practice

Three mechanisms, layered:

1. **Prompt** — rule 1 states it, rule 7 forbids inventing.
2. **Tools** — facts are only obtainable by calling one.
3. **Evidence** — `tool_trace` and `citations` are returned with every reply and
   rendered in the UI as expandable chips.

The third is the one that makes the first two verifiable. A reviewer can open any answer
and see exactly which tool produced which value, with arguments and timing. Hallucinated
facts have nowhere to hide, because a claim with no corresponding tool call is visibly
unsupported.

---

## 5.7 The offline planner

`MockProvider` implements `BaseLLMProvider` and speaks the same protocol — emits
`ToolUse`, receives `tool_result`, renders prose. Swapping it for Claude changes one
factory function and nothing else.

**Routing** is ordered pattern matching, and the order encodes real intent:

```
1  human / agent / escalate               → escalate_to_human
2  policy / terms / charges / how long    → search_knowledge_base   ← before actions
3  cancel + order                         → cancel_order
4  return / refund / damaged / wrong item → initiate_return
5  track / where is my order / delayed    → track_shipment
6  order status / ORD-…                   → lookup_order
7  in stock / available / do you have     → check_product_availability
8  recommend / suggest / looking for      → recommend_products
9  store / nearby / pickup                → find_nearby_store
10 my account / loyalty / points          → get_customer_profile
11 complaint / terrible / angry           → create_support_ticket
default                                   → search_knowledge_base
```

Rule 2 sits deliberately above the action rules. Without it, *"what is your refund
**policy**"* matched the refund pattern and started an actual refund — a bug caught by
the grounding test, which asserts that a policy question produces citations.

**Rendering** is a dispatch table over tool name, formatting currency, humanising status
strings, and trimming retrieved passages to whole sentences so an answer never begins
mid-thought.

**What it is not:** a language model. It does not paraphrase, reason about novel
situations, or handle genuinely ambiguous phrasing. It exists so the *system* is
demonstrable and testable without cost or network — not to replace an LLM.

---

## 5.8 Failure modes and responses

| Failure | Response |
|---|---|
| Tool raises | Caught, returned as `{"error": …}`; model sees it and recovers |
| Two tool errors in a conversation | Escalate (`TOOL_ERROR`) |
| Tool-iteration ceiling reached | Stop, apologise, escalate |
| LLM provider unreachable | Retry once on the fallback model, then `provider_error` |
| Empty model output | Output guardrail replaces it with the fallback message |
| Retrieval returns nothing | Agent says so and offers a ticket — it does not guess |
| Stale embedding dimensions | Mismatched vectors skipped, warning logged, reindex advised |
| Customer not signed in | Account tools return a friendly sign-in prompt, not an error |

---

## 5.9 Extending the agent

Adding a capability is one function:

```python
@tool(
    "check_warranty_status",
    "Look up remaining manufacturer warranty for a purchased item, with the "
    "expiry date and what is covered. Use when the customer asks whether a "
    "repair is free.",
    _obj({"order_number": _str("Order the item was bought on."),
           "sku": _str("Product SKU, if known.")}, ["order_number"]),
)
async def check_warranty_status(ctx: ToolContext, order_number: str,
                                sku: str | None = None) -> dict[str, Any]:
    order, error = await _resolve_order(ctx, order_number, False)
    if error:
        return error
    ...
    return {"covered": True, "expires_on": "2027-03-14", "…": "…"}
```

The decorator registers both the schema and the handler. The orchestrator picks it up
automatically, the UI renders it in the trace, and analytics starts counting it — no
other file changes.

**Writing a good description matters more than the code.** It is the only thing the
model reads when deciding whether to call the tool. State what it returns, when to use
it, and — where it matters — when *not* to.
