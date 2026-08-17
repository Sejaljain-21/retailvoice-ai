# 1 · Software Requirements Specification

**Project:** RetailVoice AI — Customer Support & Voice Agent
**Domain:** E-commerce and retail
**Version:** 1.0

---

## 1.1 Problem statement

Retail support is dominated by a small number of repetitive, data-lookup questions.
Published industry breakdowns and the seeded traffic in this project agree on the
shape: *where is my order*, *how do I return this*, *when will my refund arrive*,
*is this in stock*. Each is trivially answerable **if** the answering system can read
the order record, the courier scan and the current policy.

Traditional support has two failure modes:

| Approach | Failure |
|---|---|
| Human agents | Expensive, queue at peak, inconsistent policy recall, no 24×7 |
| Scripted chatbots / IVR | Cannot see the customer's data, dead-ends on anything off-script, actively disliked |
| Naive LLM chatbot | Fluent but **ungrounded** — invents order numbers, refund windows and delivery dates |

The third failure is the one this project is built around. A support agent that
confidently states a wrong refund timeline is worse than no agent at all, because the
customer acts on it.

**Thesis:** an LLM should never be the *source* of a fact in customer support. It should
be the *interface* to facts retrieved from systems of record. Every claim about an
order, a price or a policy must trace back to a tool call.

---

## 1.2 Objectives

| # | Objective | Measurable outcome |
|---|---|---|
| O1 | Resolve routine support requests without a human | Containment rate ≥ 70 % |
| O2 | Never state an unverified fact | 100 % of order/stock/policy claims backed by a tool call |
| O3 | Support voice as a first-class channel | Full duplex call: speech in, spoken answer out, barge-in |
| O4 | Escalate reliably, not optimistically | Deterministic rules that fire independently of the model |
| O5 | Protect customer data | PII masked before storage; ownership enforced on every record |
| O6 | Be measurable | Containment, deflection, CSAT, AHT, per-tool success and latency |
| O7 | Run with zero external dependencies | Full demo with no API keys, no model downloads, no services |

---

## 1.3 Stakeholders

| Stakeholder | Needs |
|---|---|
| **Customer** | A correct answer fast, in chat or by voice, without repeating themselves |
| **Support agent** | Only the conversations that genuinely need a human, with full context attached |
| **Support supervisor** | Queue health, SLA breaches, escalation reasons, CSAT trend |
| **Knowledge manager** | Edit a policy once and have the agent's answers change immediately |
| **Engineering** | Swap LLM/STT/TTS providers without touching business logic |
| **Compliance** | Auditable record of every automated action; no card data or OTPs retained |

---

## 1.4 Scope

### In scope
- Chat and voice support across web chat, voice, phone, WhatsApp and email channels
  (channel is a first-class attribute on every conversation).
- Order operations: lookup, tracking, cancellation, returns with RMA and pickup.
- Catalogue operations: stock check, recommendations, delivery estimate, store locator.
- Policy answers grounded in a retrievable, editable knowledge base.
- Ticketing with priority derivation and SLA tracking.
- Human handoff with transcript, and a console for agents to reply.
- Analytics over the whole system.

### Out of scope
- Real payment capture (payment *status* is modelled; no gateway integration).
- Live courier APIs (tracking events are modelled and seeded).
- Warehouse / ERP synchronisation.
- Native mobile applications.
- Multi-tenancy (a single retail brand is assumed).

---

## 1.5 Functional requirements

### FR-1 Conversation
| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | Accept a customer message on any channel and return a reply | Must |
| FR-1.2 | Maintain multi-turn context within a conversation | Must |
| FR-1.3 | Allow anonymous visitors to converse before signing in, and claim the thread on sign-in | Should |
| FR-1.4 | Classify intent, sentiment and language on every turn | Must |
| FR-1.5 | Offer contextual quick-reply suggestions | Could |

### FR-2 Grounding
| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Every order, stock or price claim must originate from a tool call | Must |
| FR-2.2 | Policy answers must cite the source article with a relevance score | Must |
| FR-2.3 | Tool failures must be surfaced to the model as data, never crash the turn | Must |
| FR-2.4 | Tool arguments, results, duration and success must be persisted | Must |

### FR-3 Order operations
| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | Look up an order by number, or the customer's most recent | Must |
| FR-3.2 | Return courier tracking with scan history and a delay flag | Must |
| FR-3.3 | Cancel an unshipped order, restock items and refund | Must |
| FR-3.4 | Start a return, validating window and product returnability | Must |
| FR-3.5 | Refuse operations on another customer's order | Must |

### FR-4 Catalogue
| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | Search products with live stock levels | Must |
| FR-4.2 | Recommend in-stock products within a stated budget | Should |
| FR-4.3 | Estimate delivery date, fee and COD availability by pincode | Should |
| FR-4.4 | Locate physical stores by city or pincode | Could |

### FR-5 Knowledge base
| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | Retrieve relevant passages for a natural-language question | Must |
| FR-5.2 | Staff can create, edit and delete articles | Must |
| FR-5.3 | Edits must be re-embedded immediately — no stale index | Must |
| FR-5.4 | Support a full index rebuild | Should |

### FR-6 Escalation and ticketing
| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | Escalate on explicit request, severe negative sentiment, repeated failure, tool errors, or policy limits | Must |
| FR-6.2 | Escalation must be possible **without** the model choosing it | Must |
| FR-6.3 | Attach the full transcript to the handover ticket | Must |
| FR-6.4 | Derive priority from intent, sentiment and customer tier | Should |
| FR-6.5 | Route to the least-loaded available agent | Should |
| FR-6.6 | Track SLA due time and surface breaches | Should |

### FR-7 Voice
| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | Stream a voice session over a WebSocket | Must |
| FR-7.2 | Support both on-device and server-side speech recognition | Must |
| FR-7.3 | Speak replies aloud | Must |
| FR-7.4 | Support barge-in (customer interrupts the agent) | Should |
| FR-7.5 | Constrain voice replies to a speakable length and strip markdown | Must |
| FR-7.6 | Provide a non-streaming REST equivalent for one turn | Should |

### FR-8 Analytics
| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | Report containment, deflection, CSAT, AHT and first-response latency | Must |
| FR-8.2 | Break down volume by intent, channel and sentiment | Must |
| FR-8.3 | Report per-tool call count, success rate and latency | Must |
| FR-8.4 | Estimate LLM token spend | Could |

### FR-9 Identity and access
| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | Register and sign in with email and password | Must |
| FR-9.2 | Issue short-lived access and long-lived refresh tokens | Must |
| FR-9.3 | Enforce roles: customer, agent, supervisor, admin | Must |
| FR-9.4 | Customers see only their own orders, tickets and conversations | Must |

---

## 1.6 Non-functional requirements

| ID | Requirement | Target | How it is met |
|---|---|---|---|
| NFR-1 | Response latency | < 3 s p95 for a tool-using turn | Local NLU, pre-fetched RAG, capped tool iterations |
| NFR-2 | Availability | Stateless API, restartable | No in-process session state; conversation state in the DB |
| NFR-3 | Data protection | No card numbers, OTPs, emails or phone numbers in storage | Regex redaction before persistence, tested |
| NFR-4 | Auditability | Every automated action reconstructable | `tool_call_logs` with arguments, result, duration, success |
| NFR-5 | Portability | Same code on SQLite and PostgreSQL | Async SQLAlchemy, portable column types, no vendor SQL |
| NFR-6 | Extensibility | New provider without touching business logic | Abstract base classes + factory per provider family |
| NFR-7 | Zero-setup demo | Runs with an empty `.env` | Offline planner, hashing embedder, browser speech |
| NFR-8 | Accessibility | Keyboard navigable, labelled controls, visible focus | Semantic HTML, ARIA labels, focus-visible rings |
| NFR-9 | Testability | Deterministic without network | Mock providers, fixed-seed dataset, 91 tests |

---

## 1.7 Primary use cases

### UC-1 — Track a delayed order
**Actor:** signed-in customer
**Trigger:** "Where is my order? It's late."

1. NLU classifies `track_shipment`, sentiment slightly negative.
2. Guardrails pass; the turn is persisted.
3. The agent calls `track_shipment` with `most_recent=true`.
4. The tool returns carrier, last scan, ETA and `is_delayed=true`.
5. The agent acknowledges the delay, states the facts and offers a remedy.

**Alternate:** if sentiment is below −0.55, escalation rules fire *before* the reply is
returned and a human is assigned.

### UC-2 — Return a damaged item
**Actor:** signed-in customer

1. Agent asks for the reason (one question at a time).
2. Calls `initiate_return`, which validates delivery status, product returnability and
   the return window against the product's own policy.
3. On success: RMA issued, refund amount computed, free pickup booked.
4. On window expiry: the tool refuses and offers an exception request instead.

### UC-3 — Policy question
**Actor:** anonymous visitor

1. Retrieval pre-fetches candidate passages before the model is called.
2. The agent calls `search_knowledge_base` and answers from the returned passages only.
3. The reply carries citations with relevance scores, shown in the UI.

### UC-4 — Escalation the model didn't request
**Actor:** frustrated customer

1. Customer writes an angry message; sentiment scores −0.8.
2. `policy.should_escalate` fires on the sentiment rule.
3. A ticket is created at `urgent` priority, the transcript attached, the least-loaded
   agent assigned, and the handoff message appended to the reply.

### UC-5 — Voice call
**Actor:** any customer

1. Client opens `/ws/voice`; server replies `ready` with provider capabilities.
2. Speech is recognised on-device and sent as a `text` frame.
3. Server streams `thinking` → `tool_call` → `reply_delta` → `reply` → `audio`.
4. Reply is spoken; a `barge_in` frame cancels playback.

### UC-6 — Knowledge edit propagates
**Actor:** admin

1. Admin edits an article in the console.
2. `PATCH /knowledge/{id}` re-chunks and re-embeds it in the same request.
3. The next customer question retrieves the new text — no rebuild step.

---

## 1.8 Assumptions and constraints

**Assumptions**
- One retail brand, one currency (INR), primarily English with Hindi/Hinglish support.
- Order and catalogue data are authoritative in this system (in production they would
  be read through an ERP adapter, which the tool layer already isolates).
- Customers authenticate by email and password.

**Constraints**
- No paid service may be *required* to run or evaluate the project.
- Browser speech recognition limits on-device STT to Chrome, Edge and Safari.
- SQLite has no native vector type, so embeddings are stored as JSON arrays and scored
  in the application — acceptable to a few thousand chunks, documented as the scaling
  boundary.

---

## 1.9 Acceptance criteria

The project is complete when:

1. A user can hold a multi-turn chat **and** a voice call that ends in a real state
   change (a cancellation or a return) visible in the database.
2. Every order/stock/policy claim in a reply corresponds to a logged tool call.
3. An angry message escalates without the model requesting it, producing an assigned
   ticket with the transcript.
4. A customer cannot read another customer's order — enforced and tested.
5. An email or phone number in a message never appears in stored data.
6. The analytics dashboard reports containment, CSAT and per-tool metrics from real
   recorded traffic.
7. The whole system starts from a clean checkout with no API keys.
8. The test suite passes without network access.

All eight are met; see [`06-testing-and-evaluation.md`](06-testing-and-evaluation.md).
