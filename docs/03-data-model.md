# 3 · Data model

16 tables, async SQLAlchemy 2.0, portable across SQLite and PostgreSQL.

---

## 3.1 Entity-relationship overview

```
                            ┌──────────────┐
                            │    users     │
                            │ role, email  │
                            └──┬───┬───┬───┘
              ┌────────────────┘   │   └────────────────┐
              │ 1:1                │ 1:N               │ 1:N
   ┌──────────▼────────┐  ┌────────▼────────┐  ┌───────▼────────┐
   │ customer_profiles │  │     orders      │  │ conversations  │
   │ tier, points, LTV │  │ status, totals  │  │ channel, intent│
   └───────────────────┘  └──┬───┬───┬──────┘  │ sentiment,     │
                             │   │   │         │ escalated      │
              ┌──────────────┘   │   └───────┐ └──┬──────┬──────┘
              │ 1:N              │ 1:1       │1:N    │1:N  │1:1
   ┌──────────▼──────┐ ┌─────────▼──────┐ ┌──▼──────▼─┐ ┌─▼────────┐
   │  order_items    │ │   shipments    │ │ messages  │ │ feedback │
   │ qty, unit_price │ │ AWB, events[]  │ │ role,     │ │ CSAT/NPS │
   └────────┬────────┘ └────────────────┘ │ content,  │ └──────────┘
            │ N:1                          │ citations │
   ┌────────▼────────┐  ┌───────────────┐ └───────────┘
   │    products     │  │return_requests│      │
   │ sku, stock,     │  │ RMA, refund   │ ┌────▼──────────┐
   │ return policy   │  └───────────────┘ │tool_call_logs │
   └────────┬────────┘                    │ args, result, │
            │ N:1                         │ duration      │
   ┌────────▼────────┐                    └───────────────┘
   │   categories    │
   └─────────────────┘                    ┌───────────────┐
                                          │    tickets    │
   ┌─────────────────┐                    │ SLA, priority │
   │ store_locations │                    └───────────────┘
   └─────────────────┘
                        ┌──────────────┐  1:N  ┌──────────────┐
                        │ kb_documents │──────▶│  kb_chunks   │
                        │ title, body  │       │ embedding[]  │
                        └──────────────┘       └──────────────┘
```

---

## 3.2 Conventions

| Convention | Reason |
|---|---|
| Primary keys are 32-char hex UUIDs (`uuid4().hex`) | Portable across backends, safe to expose, no sequence contention |
| Enums stored as `String`, exposed as Python `StrEnum` | Adding a value needs no migration; type safety stays in the app |
| `created_at` / `updated_at` on every table | Analytics and audit both need them |
| `DateTime(timezone=True)`, always UTC | Avoids the entire timezone class of bugs |
| Structured payloads in `JSON` columns | Works identically on SQLite and PostgreSQL |
| `lazy="selectin"` on hot relationships | Prevents async lazy-load errors and N+1 queries |

---

## 3.3 Identity

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | String(32) | PK |
| `email` | String(255) | Unique, indexed |
| `hashed_password` | String(255) | bcrypt, cost 12 |
| `full_name` | String(160) | |
| `phone` | String(32) | Nullable |
| `role` | String(24) | `customer` · `agent` · `supervisor` · `admin`, indexed |
| `is_active` | Boolean | Deactivation without deletion |
| `locale` | String(12) | Default `en-IN` |
| `last_login_at` | DateTime | |

### `customer_profiles` — 1:1 with `users`
| Column | Type | Notes |
|---|---|---|
| `tier` | String(16) | `standard` · `silver` · `gold` · `platinum` |
| `loyalty_points` | Integer | Earned at 1 point per ₹100 |
| `lifetime_value` | Float | Maintained on order creation |
| `total_orders` | Integer | |
| `default_address`, `city`, `pincode` | Text / String | Used for delivery estimates |
| `notes` | Text | Goodwill gestures are appended here — an audit trail |

The tier drives real behaviour: it feeds ticket priority derivation and triggers earlier
escalation for gold and platinum customers.

---

## 3.4 Catalogue

### `products`
| Column | Type | Notes |
|---|---|---|
| `sku` | String(48) | Unique, indexed |
| `name`, `brand` | String | Both indexed for search |
| `price`, `mrp` | Float | `discount_percent` derived |
| `stock_quantity` | Integer | Decremented on order, restored on cancel |
| `rating`, `review_count` | Float / Integer | Used to rank recommendations |
| `attributes` | JSON | `{"colour": "...", "warranty_months": 12}` |
| `tags` | JSON | Search hints |
| `return_window_days` | Integer | **Per product**, not global |
| `is_returnable` | Boolean | False for consumables and cosmetics |

`return_window_days` and `is_returnable` are the fields the `initiate_return` tool
validates against. Policy lives on the product row, so a policy change is a data change
rather than a code change.

### `categories`, `store_locations`
Straightforward reference tables. Stores carry `city`, `pincode`, `opening_hours`,
`supports_pickup` and coordinates, powering the store-locator tool.

---

## 3.5 Orders

### `orders`
| Column | Type | Notes |
|---|---|---|
| `order_number` | String(32) | `ORD-YYMM` + 6 digits, unique, indexed |
| `customer_id` | FK → users | Indexed |
| `status` | String(24) | See lifecycle below, indexed |
| `payment_status` | String(24) | `pending` · `paid` · `failed` · `refunded` · `partially_refunded` |
| `subtotal`, `shipping_fee`, `discount`, `tax`, `total_amount` | Float | Computed at creation |
| `placed_at`, `expected_delivery`, `delivered_at`, `cancelled_at` | DateTime | |
| `coupon_code` | String(32) | |

**Order lifecycle**

```
pending ─▶ confirmed ─▶ packed ─▶ shipped ─▶ out_for_delivery ─▶ delivered
   │           │          │                                          │
   └───────────┴──────────┘                                          ▼
        cancellable window                                   returned
        (is_cancellable = True)                       (via return_requests)
```

`Order.is_cancellable` is a property on the model, so the API, the agent tool and the
frontend all read the same rule rather than three copies of it.

### `order_items`
Denormalises `product_name`, `sku`, `unit_price` and `attributes` at purchase time.
Deliberate: an invoice must show what was bought at the price paid, even after the
catalogue changes.

### `shipments` — 1:1 with `orders`
| Column | Type | Notes |
|---|---|---|
| `tracking_number` | String(48) | Unique, indexed |
| `carrier`, `status`, `current_location` | String | |
| `estimated_delivery`, `delivered_at` | DateTime | |
| `events` | JSON | `[{"at", "status", "location"}]` scan history |

A shipment is *late* when `estimated_delivery < now` and status is not `delivered` —
computed in `shipment_snapshot()` and surfaced to the agent as `is_delayed`.

### `return_requests`
| Column | Type | Notes |
|---|---|---|
| `rma_number` | String(32) | Unique, indexed |
| `status` | String(24) | `requested` → `approved` → `picked_up` → `refunded` (or `rejected`) |
| `refund_amount`, `refund_method` | Float / String | |
| `pickup_scheduled_at` | DateTime | |
| `created_by_agent` | Boolean | Separates AI-created from self-service returns |

---

## 3.6 Support

### `conversations`
| Column | Type | Notes |
|---|---|---|
| `customer_id` | FK → users, nullable | Null for anonymous visitors |
| `anonymous_key` | String(64) | Lets a guest thread survive until sign-in |
| `channel` | String(24) | `web_chat` · `voice` · `email` · `whatsapp` · `phone` |
| `status` | String(24) | `active` · `resolved` · `escalated` · `abandoned` |
| `primary_intent` | String(40) | First non-trivial intent, indexed |
| `last_sentiment`, `sentiment_score` | String / Float | Drives escalation |
| `is_escalated`, `escalated_at`, `escalation_reason` | | Indexed |
| `assigned_agent_id` | FK → users | |
| `resolved_by_ai` | Boolean | **The containment metric** |
| `message_count`, `total_tokens`, `total_latency_ms`, `voice_seconds` | | Telemetry |
| `conversation_metadata` | JSON | Goodwill vouchers, client hints |

> Named `conversation_metadata`, not `metadata` — `metadata` is reserved on the
> SQLAlchemy declarative base.

### `messages`
| Column | Type | Notes |
|---|---|---|
| `role` | String(20) | `user` · `assistant` · `system` · `tool` · `human_agent` |
| `content` | Text | **Already redacted** when stored |
| `intent`, `intent_confidence`, `sentiment`, `sentiment_score` | | Per-turn NLU |
| `tool_calls` | JSON | Summary shown in the UI |
| `citations` | JSON | Retrieved passages with scores |
| `latency_ms`, `tokens_in`, `tokens_out`, `model` | | Cost and performance |
| `audio_duration_ms`, `transcript_confidence` | | Voice turns only |
| `was_redacted` | Boolean | True when PII was masked |

`human_agent` is a distinct role from `assistant` so the UI can label a real person as a
real person — customers should never be misled about who they are talking to.

### `tool_call_logs` — the audit trail
| Column | Type | Notes |
|---|---|---|
| `tool_name` | String(64) | Indexed |
| `arguments`, `result` | JSON | Full request and response |
| `success`, `error` | Boolean / Text | |
| `duration_ms` | Integer | |

One row per invocation. This table answers "why did the agent say that?" and feeds the
per-tool reliability panel in analytics.

### `tickets`
| Column | Type | Notes |
|---|---|---|
| `ticket_number` | String(24) | `TKT-YYMMDD-XXXXX`, unique |
| `status` | String(24) | `open` · `in_progress` · `waiting_customer` · `resolved` · `closed` |
| `priority` | String(16) | Derived from intent + sentiment + tier |
| `sla_due_at` | DateTime | urgent 2 h · high 8 h · medium 24 h · low 72 h |
| `first_response_at`, `resolved_at` | DateTime | |
| `created_by_agent` | Boolean | AI-opened vs human-opened |
| `description` | Text | Includes the full transcript on escalation |

### `feedback`
CSAT `rating` 1–5, `resolved` boolean, optional `nps` 0–10 and free-text comment.
One row per conversation.

---

## 3.7 Knowledge base

### `kb_documents`
`title`, unique `slug`, `category`, `content`, `tags`, `is_published`, `version`,
`view_count`, `helpful_count`. `version` increments on every content edit.

### `kb_chunks` — the retrieval index
| Column | Type | Notes |
|---|---|---|
| `document_id` | FK → kb_documents, cascade delete | Indexed |
| `chunk_index` | Integer | Order within the document |
| `content` | Text | The passage shown as a citation |
| `embedding` | JSON | Float array — portable across backends |
| `embedding_model` | String(80) | Stale-index detection |
| `norm` | Float | Pre-computed vector norm |

**Why JSON rather than pgvector.** A JSON array works identically on SQLite and
PostgreSQL, so the project runs with zero infrastructure. The cost is a full scan per
query, acceptable to roughly 5,000 chunks. `embedding_model` is stored so that a
dimension mismatch after a model change is detected and logged rather than producing
silently wrong results.

---

## 3.8 Indexing

| Table | Indexed | Why |
|---|---|---|
| `users` | `email`, `role` | Login, staff filters |
| `orders` | `order_number`, `customer_id`, `status` | The three lookup paths |
| `shipments` | `tracking_number`, `order_id` | Tracking-number lookup |
| `conversations` | `customer_id`, `status`, `channel`, `is_escalated`, `primary_intent` | Console filters and analytics group-bys |
| `messages` | `conversation_id`, `role` | Transcript loads |
| `tool_call_logs` | `conversation_id`, `tool_name` | Per-tool aggregation |
| `tickets` | `ticket_number`, `status`, `priority`, `customer_id` | Queue filters |
| `kb_chunks` | `document_id` | Re-index by document |

---

## 3.9 Seed dataset

Fixed RNG seed (`20250816`) so the demo is reproducible.

| Entity | Count | Shaped for |
|---|---|---|
| Users | 9 | 4 staff (admin, supervisor, 2 agents), 5 customers across all tiers |
| Categories / products | 6 / 21 | Includes out-of-stock, non-returnable, low-stock items |
| Stores | 6 | Six metros, for the locator tool |
| Orders | 10 | **One per lifecycle state**, plus one deliberately late and one past its return window |
| Shipments | 6 | Full scan histories |
| Return requests | 1 | An in-flight RMA |
| KB articles → chunks | 14 → 30 | Real help-centre prose with concrete numbers |
| Conversations | 36 | 12 scripts × 3 passes over 14 days |
| Tickets | 9 | From the escalated conversations |
| Feedback | 36 | Produces a realistic ~4.0 CSAT |

The order set is designed so every agent tool has something meaningful to act on: a
cancellable order, a delivered order inside its return window, one outside it, and a
late shipment that triggers the delay path.
