# 4 · API reference

Base URL `/api/v1` · interactive docs at `/docs` (Swagger) and `/redoc`.

---

## 4.1 Conventions

**Authentication** — `Authorization: Bearer <access_token>`.
Access tokens last 12 hours, refresh tokens 14 days. The client refreshes
automatically on a 401 and retries the original request once.

**Error shape** — every failure returns the same envelope:

```json
{ "error": { "code": "not_found", "message": "Order not found.", "details": {} } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Request body failed validation |
| `unauthorized` | 401 | Missing, invalid or expired token |
| `forbidden` | 403 | Authenticated but not permitted |
| `not_found` | 404 | No such record |
| `conflict` | 409 | Valid request, invalid state (e.g. cancelling a shipped order) |
| `provider_error` | 502 | An LLM / STT / TTS provider failed |
| `internal_error` | 500 | Unhandled — logged server-side, generic to the client |

**Pagination** — `?page=1&page_size=20` (max 100), returning
`{items, total, page, page_size}`.

**Access levels** — 🔓 public · 🔑 any signed-in user · 👔 staff (agent / supervisor /
admin).

Every response carries `X-Process-Time-Ms`.

---

## 4.2 System

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/health` | 🔓 | Liveness: status, version, uptime |
| GET | `/ready` | 🔓 | Readiness: database plus every provider |
| GET | `/capabilities` | 🔓 | What this deployment can do |

`/capabilities` is what the frontend's runtime badge reads:

```json
{
  "llm": { "provider": "mock", "model": "mock-planner-v1", "max_tool_iterations": 6 },
  "speech": { "stt_provider": "browser", "stt_client_side": true,
              "tts_provider": "browser", "tts_client_side": true },
  "retrieval": { "embedding_provider": "hashing-v1", "dim": 384, "top_k": 4 },
  "tools": ["lookup_order", "track_shipment", "…"],
  "features": { "pii_redaction": true, "anonymous_order_lookup": true }
}
```

---

## 4.3 Authentication

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/auth/register` | 🔓 | Create a customer account |
| POST | `/auth/login` | 🔓 | Exchange credentials for tokens |
| POST | `/auth/refresh` | 🔓 | New access token from a refresh token |
| GET | `/auth/me` | 🔑 | Current user with profile |
| PATCH | `/auth/me` | 🔑 | Update name, phone, address, language |

```http
POST /api/v1/auth/login
{ "email": "customer@retailvoice.ai", "password": "Demo@1234" }
```
```json
{
  "user": { "id": "…", "full_name": "Aarav Sharma", "role": "customer",
            "profile": { "tier": "gold", "loyalty_points": 2840 } },
  "tokens": { "access_token": "eyJ…", "refresh_token": "eyJ…",
              "token_type": "bearer", "expires_in": 43200 }
}
```

---

## 4.4 Catalogue

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/catalog/categories` | 🔓 | All categories |
| GET | `/catalog/products` | 🔓 | Search and filter |
| GET | `/catalog/products/{id\|sku}` | 🔓 | One product |
| GET | `/catalog/stores` | 🔓 | Stores by city or pincode |

`/catalog/products` accepts `q`, `category` (slug), `brand`, `min_price`, `max_price`,
`in_stock_only`, and `sort` ∈ `relevance` · `price_asc` · `price_desc` · `rating` ·
`newest`.

---

## 4.5 Orders

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/orders` | 🔑 | Own orders (staff: `?all_customers=true`) |
| POST | `/orders` | 🔑 | Place an order |
| GET | `/orders/{ref}` | 🔑 | One order — accepts id **or** `ORD-…` number |
| POST | `/orders/{ref}/cancel` | 🔑 | Cancel, restock and refund |
| POST | `/orders/{ref}/returns` | 🔑 | Start a return |
| GET | `/orders/{ref}/tracking` | 🔑 | Courier snapshot |

Ownership is enforced on every one of these: a customer requesting another customer's
order receives `403 forbidden`.

```http
POST /api/v1/orders/ORD-2508123456/cancel
{ "reason": "Ordered the wrong variant" }
```

Returns the updated order, or `409 conflict` with an explanation if it has already
shipped.

---

## 4.6 Chat and conversations

| Method | Path | Access | Purpose |
|---|---|---|---|
| POST | `/chat/message` | 🔓 | **Send a message, get the agent's reply** |
| POST | `/chat/conversations` | 🔓 | Open a conversation explicitly |
| GET | `/chat/conversations` | 🔑 | List (staff see all; `?assigned_to_me`, `?escalated_only`) |
| GET | `/chat/conversations/{id}` | 🔓* | Full transcript |
| POST | `/chat/conversations/{id}/close` | 🔓* | Mark resolved or abandoned |
| POST | `/chat/conversations/{id}/handoff` | 🔓* | Explicit "talk to a human" |
| POST | `/chat/conversations/{id}/reply` | 👔 | Post as a human agent |
| POST | `/chat/conversations/{id}/feedback` | 🔓* | Submit CSAT |

\* Ownership-checked when a token is present.

### The main endpoint

```http
POST /api/v1/chat/message
{
  "message": "Where is my order?",
  "conversation_id": null,
  "channel": "web_chat",
  "voice_mode": false,
  "anonymous_key": "guest-a1b2c3"
}
```

```json
{
  "conversation_id": "5f2c…",
  "message_id": "9ab1…",
  "reply": "Your parcel is **out for delivery** with BlueDart…",
  "intent": "track_shipment",
  "intent_confidence": 0.86,
  "sentiment": "neutral",
  "sentiment_score": 0.0,
  "citations": [],
  "tool_trace": [
    { "tool": "track_shipment",
      "arguments": { "most_recent": true },
      "result": { "found": true, "carrier": "BlueDart", "is_delayed": false },
      "success": true, "duration_ms": 42, "error": null }
  ],
  "escalated": false,
  "escalation_reason": null,
  "suggested_replies": ["It's late - help", "Change delivery date", "Talk to an agent"],
  "handoff_ticket_number": null,
  "latency_ms": 612,
  "model": "mock-planner-v1",
  "tokens_in": 148,
  "tokens_out": 62
}
```

`tool_trace` and `citations` are the grounding evidence — the UI renders them as
expandable "actions" and "sources" chips beneath the reply.

Setting `voice_mode: true` swaps in the voice system prompt, which caps the reply at
~55 words and forbids markdown.

---

## 4.7 Voice

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/voice/config` | 🔓 | Provider capabilities before a call |
| POST | `/voice/transcribe` | 🔓 | Audio → text |
| POST | `/voice/synthesize` | 🔓 | Text → audio |
| POST | `/voice/turn` | 🔓 | **One complete turn**: audio/text in, audio out |
| POST | `/voice/tts-preview` | 🔓 | Playback check |
| WS | `/ws/voice` | 🔓 | Streaming session |

### One-shot turn

`multipart/form-data`, either `audio` (a file) or `text` (a client-side transcript):

```http
POST /api/v1/voice/turn
audio=@question.webm & language=en & speak=true
```
```json
{
  "transcript": { "text": "Where is my order?", "confidence": 0.94,
                  "duration_ms": 1820, "provider": "whisper" },
  "reply": { "...": "the same AgentReply shape as /chat/message" },
  "audio": { "audio_base64": "UklGR…", "mime_type": "audio/wav",
             "duration_ms": 4100, "use_client_tts": false }
}
```

When `TTS_PROVIDER=browser`, `use_client_tts` is `true` and `audio_base64` is empty —
the client speaks the `text` field with `SpeechSynthesis` instead.

---

## 4.8 WebSocket protocol — `/ws/voice`

```
ws://localhost:8000/ws/voice?token=<jwt>&conversation_id=<id>&language=en
```

The JWT is a query parameter because browsers cannot set headers on a WebSocket
handshake. Omit it for an anonymous session.

### Client → server

| Type | Payload | Meaning |
|---|---|---|
| `start` | — | Begin capturing |
| `audio_chunk` | `data`: base64 audio | A recorder slice (server-side STT only) |
| `audio_end` | — | Utterance finished; transcribe now |
| `text` | `data`: transcript | Browser already recognised the speech |
| `barge_in` | — | Customer interrupted; stop speaking |
| `stop` | — | End the call |
| `ping` | — | Keepalive |

### Server → client

| Type | Payload | Meaning |
|---|---|---|
| `ready` | conversation_id, providers, greeting | Handshake complete |
| `final_transcript` | text, confidence | What was heard |
| `thinking` | intent, sentiment | NLU finished |
| `tool_call` | tool, arguments | About to call a tool |
| `tool_result` | tool, success, duration_ms | Tool returned |
| `reply_delta` | text | A six-word group of the answer |
| `reply` | full reply + telemetry | Complete answer |
| `audio` | audio_base64 \| use_client_tts | Speak this |
| `escalated` | reason, ticket_number | Handed to a human |
| `error` | message, code | Recoverable problem |
| `closed` | turns | Session ended |

Every frame carries `type`, `data`, `conversation_id` and a monotonic `seq`.

**A typical turn:**

```
→ {"type":"text","data":"where is my order"}
← {"type":"final_transcript","data":{"text":"where is my order","confidence":1.0}}
← {"type":"thinking","data":{"intent":"track_shipment","sentiment":"neutral"}}
← {"type":"tool_call","data":{"tool":"track_shipment","arguments":{…}}}
← {"type":"tool_result","data":{"tool":"track_shipment","success":true,"duration_ms":42}}
← {"type":"reply_delta","data":{"text":"Your parcel is out for delivery "}}
← {"type":"reply","data":{"text":"…","speakable":"…","suggested_replies":[…]}}
← {"type":"audio","data":{"use_client_tts":true,"text":"…"}}
```

---

## 4.9 Tickets

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/tickets` | 🔑 | Own tickets; staff see all |
| POST | `/tickets` | 🔑 | Raise a ticket |
| GET | `/tickets/stats` | 👔 | Queue counts and SLA breaches |
| GET | `/tickets/{id\|number}` | 🔑 | One ticket |
| PATCH | `/tickets/{id}` | 👔 | Update status, priority, assignee, resolution |
| POST | `/tickets/{id}/claim` | 👔 | Assign to self and start work |

Results are ordered urgent → high → medium → low, then newest first.

---

## 4.10 Knowledge base

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/knowledge/search` | 🔓 | **Hybrid semantic + keyword search** |
| GET | `/knowledge` | 🔓 | List articles |
| GET | `/knowledge/categories` | 🔓 | Categories with counts |
| GET | `/knowledge/stats` | 🔓 | Index size and embedding model |
| GET | `/knowledge/{id\|slug}` | 🔓 | One article (increments views) |
| POST | `/knowledge` | 👔 | Create — embedded immediately |
| PATCH | `/knowledge/{id}` | 👔 | Update — re-embedded immediately |
| DELETE | `/knowledge/{id}` | 👔 | Delete with its chunks |
| POST | `/knowledge/reindex` | 👔 | Rebuild every embedding |
| POST | `/knowledge/{id}/helpful` | 🔓 | Mark helpful |

```http
GET /api/v1/knowledge/search?q=how%20long%20does%20a%20UPI%20refund%20take&top_k=3
```
```json
{
  "query": "how long does a UPI refund take",
  "hits": [
    { "chunk_id": "…", "document_id": "…",
      "title": "Refund timelines by payment method",
      "slug": "refund-timelines-by-payment-method",
      "category": "refunds",
      "snippet": "Refunds are initiated within 24 hours of…",
      "score": 0.3771 }
  ],
  "took_ms": 8
}
```

Creating or editing an article re-chunks and re-embeds it **inside the same request**,
so the agent's answers change immediately — there is no rebuild step and no stale index.

---

## 4.11 Analytics — 👔 staff only

| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/dashboard` | Everything in one round-trip |
| GET | `/analytics/kpis` | Headline metrics |
| GET | `/analytics/intents` | Volume and escalation rate per intent |
| GET | `/analytics/channels` | Volume and containment per channel |
| GET | `/analytics/timeseries` | Daily conversations, escalations, sentiment |
| GET | `/analytics/tools` | Per-tool calls, success rate, latency |
| GET | `/analytics/sentiment` | Sentiment distribution |

All accept `?days=` (1–365, default 30).

```json
{
  "kpis": {
    "total_conversations": 36, "containment_rate": 75.0, "deflection_rate": 75.0,
    "avg_csat": 4.0, "csat_responses": 36, "avg_first_response_ms": 1704.2,
    "escalated": 9, "open_tickets": 5, "total_voice_minutes": 30.6,
    "total_tokens": 97142, "estimated_cost_usd": 0.7594
  },
  "intents": [ { "intent": "delivery_delay", "count": 3, "percentage": 8.3,
                 "avg_sentiment": -0.72, "escalation_rate": 100.0 } ],
  "tools":   [ { "tool": "track_shipment", "calls": 6,
                 "success_rate": 100.0, "avg_duration_ms": 62.3 } ]
}
```

Metric definitions are in [`06-testing-and-evaluation.md`](06-testing-and-evaluation.md).

---

## 4.12 Rate limits and payload caps

| Limit | Value | Where |
|---|---|---|
| Audio upload | 12 MB | `/voice/transcribe`, `/voice/turn` |
| WebSocket audio buffer | 12 MB | `/ws/voice` |
| Voice session | 900 s | Configurable |
| Chat message | 4,000 chars | Pydantic validation |
| Tool iterations per turn | 6 | Then the turn escalates |
| Page size | 100 | All list endpoints |

There is no request-rate limiter — in production that belongs at the ingress
(nginx `limit_req` or an API gateway), not in the application.
