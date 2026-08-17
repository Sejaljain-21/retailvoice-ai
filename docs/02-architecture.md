# 2 · Architecture

---

## 2.1 Guiding principle

> **The language model is the interface to facts, never the source of them.**

Everything in this architecture follows from that. The LLM is deliberately confined to
three jobs — deciding *which* tool to call, deciding *what arguments* to pass, and
*wording* the result. It is never trusted with an order status, a price, a refund
window or a delivery date.

Three consequences shape the design:

1. **A tool layer sits between the model and every system of record.** Tools are plain
   async functions with JSON schemas; they are independently testable and contain no
   prompt logic.
2. **Safety decisions are deterministic.** A model can be argued out of escalating.
   Rule-based escalation cannot, so escalation runs outside the model entirely.
3. **Everything is recorded.** Tool arguments, results, durations, token counts and
   latencies are persisted — which is what makes the analytics and the evaluation
   harness possible rather than aspirational.

---

## 2.2 Component view

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (React)                             │
│                                                                         │
│  Storefront ─ widget    Support page    Agent console    Analytics      │
│                      │                                                  │
│      api.ts (REST, refresh-on-401)      speech.ts (Web Speech API)      │
└───────────┬────────────────────────────────────────┬────────────────────┘
            │ /api/v1/*                              │ /ws/voice
┌───────────▼────────────────────────────────────────▼────────────────────┐
│                            FastAPI application                          │
│                                                                         │
│  ┌───────────────────────────── API layer ─────────────────────────────┐│
│  │ auth · catalog · orders · chat · voice · tickets · knowledge ·      ││
│  │ analytics · health          + deps.py (JWT, role guards)            ││
│  └──────────────────────────────┬──────────────────────────────────────┘│
│                                 │                                       │
│  ┌──────────────────────────────▼──────────────────────────────────────┐│
│  │                       AGENT ORCHESTRATOR                            ││
│  │                                                                     ││
│  │   1 NLU ──▶ 2 input guardrails ──▶ 3 persist ──▶ 4 RAG pre-fetch    ││
│  │        ──▶ 5 LLM ⇄ tool loop ──▶ 6 output guardrails                ││
│  │        ──▶ 7 escalation rules ──▶ 8 persist + telemetry             ││
│  └───┬──────────────┬───────────────┬────────────────┬─────────────────┘│
│      │              │               │                │                  │
│  ┌───▼────┐  ┌──────▼──────┐  ┌─────▼─────┐  ┌───────▼────────┐         │
│  │  NLU   │  │ LLM provider│  │  13 tools │  │   Guardrails   │         │
│  │ intent │  │  Claude  ▲  │  │ orders    │  │ injection      │         │
│  │ senti- │  │  offline ▼  │  │ catalogue │  │ secret leak    │         │
│  │ ment   │  │  planner    │  │ knowledge │  │ hard-escalate  │         │
│  │ lang   │  └─────────────┘  │ tickets   │  │ sentiment rule │         │
│  │ PII    │                   └─────┬─────┘  └────────────────┘         │
│  └────────┘                         │                                   │
│  ┌────────────────┐  ┌──────────────▼─────────┐  ┌───────────────────┐  │
│  │ Speech (STT/TTS)│ │ Domain services        │  │ Retrieval (RAG)   │  │
│  │ browser│whisper │ │ orders · tickets ·     │  │ chunk · embed ·   │  │
│  │ deepgram│11labs │ │ analytics              │  │ hybrid rank       │  │
│  └────────────────┘  └──────────────┬─────────┘  └─────────┬─────────┘  │
└─────────────────────────────────────┼────────────────────────┼──────────┘
                                      ▼                        ▼
                        ┌──────────────────────────────────────────┐
                        │   Async SQLAlchemy · SQLite / PostgreSQL  │
                        │   16 tables incl. kb_chunks (embeddings)  │
                        └──────────────────────────────────────────┘
```

---

## 2.3 Request lifecycle — one chat turn

```
Customer: "Where is my order? It's been nine days."

 1  NLU (local, ~1 ms)
      intent    = track_shipment   (confidence 0.86)
      sentiment = negative         (score −0.34)
      language  = en
      PII       = none found

 2  Input guardrails
      injection patterns  → clean
      hard-escalate topics (legal / fraud / injury) → none

 3  Persist the customer turn (redacted text + NLU annotations)

 4  RAG pre-fetch — intent is in the pre-fetch set? No. Skipped.

 5  Build the system prompt
      persona + operating rules + voice/chat modifier
      + live context (tier, open tickets, sentiment warning)

 6  LLM ⇄ tool loop                                    ┌── max 6 iterations
      iteration 1  model → tool_use track_shipment      │
                   execute (42 ms) → {carrier, ETA,     │
                                      is_delayed: true} │
                   log to tool_call_logs                │
      iteration 2  model → text ─────────────────────── ┘

 7  Output guardrails — no secrets, non-empty → pass

 8  Escalation rules
      sentiment −0.34 > threshold −0.55        → no
      explicit human request                    → no
      gold tier + negative + ≥4 turns           → no (turn 2)
      → no escalation this turn

 9  Persist the reply with citations, tool trace, tokens, latency

    Reply: "Your parcel is out for delivery with BlueDart…
            I can see it's past the promised date, and I'm sorry."
```

Total: ~600 ms offline, ~2 s on Claude.

---

## 2.4 Voice pipeline

Two capture paths behind one WebSocket, chosen by what the server reports:

```
DEFAULT — on-device recognition (no audio leaves the browser)

  mic ─▶ Web Speech API ─▶ transcript ─▶ WS {type:"text"} ─▶ agent
                                                              │
  speaker ◀── SpeechSynthesis ◀── WS {type:"audio",           │
                                      use_client_tts:true} ◀──┘

SERVER-SIDE — when STT_PROVIDER=whisper|deepgram

  mic ─▶ MediaRecorder ─▶ base64 ─▶ WS {type:"audio_chunk"} ×N
                                    WS {type:"audio_end"}
                                          │
                                    Whisper / Deepgram
                                          ▼
                                        agent
                                          │
  speaker ◀── <audio> ◀── WS {type:"audio", audio_base64} ◀───┘
```

**Server → client event sequence for one spoken turn:**

```
final_transcript → thinking → tool_call → tool_result
                 → reply_delta ×N → reply → audio
```

`reply_delta` streams the answer in six-word groups so the transcript types out while
audio is still being produced. A `barge_in` frame from the client cancels both the
remaining deltas and playback.

**Why voice replies differ:** the system prompt swaps in a voice modifier that caps
replies at ~55 words, bans markdown, and instructs the model to spell identifiers
speakably. `to_speakable()` then strips any markdown that survives and expands `₹` to
"rupees" before synthesis.

---

## 2.5 Retrieval design

```
INDEX TIME
  article ─▶ paragraph-aware chunking ─▶ title-prefixed chunk
              (700 chars, 120 overlap        │
               snapped to sentence ends)     ▼
                                        embed ─▶ kb_chunks
                                                 (JSON vector + norm)

QUERY TIME
  question ─┬─▶ embed ──────────────▶ cosine over all chunks   0.45
            ├─▶ tokenize + stem ────▶ IDF-weighted coverage    0.40
            └─▶ tokenize + stem ────▶ title overlap            0.15
                                              │
                                     weighted sum, floor 0.12
                                              ▼
                                     max 2 chunks per article
                                              ▼
                                          top-k passages
```

**Why hybrid rather than pure vector.** The default embedder is a dependency-free
hashing embedder, which is lexically biased. On short support queries, pure cosine
picked the wrong article for 3 of 6 benchmark questions. Adding IDF-weighted lexical
coverage fixed the failure mode directly: in *"refund policy for UPI"*, `upi` appears
in one article and `policy` in half of them, so `upi` must dominate — which is exactly
what IDF encodes.

**Why stemming matters more than it looks.** Support queries and help articles disagree
constantly on word form: *cancel* vs *cancelling*, *ship* vs *shipped*. Without folding
them together, "can I cancel after shipping" retrieved the **coupons** article. A
six-rule suffix stripper took the benchmark from 3/6 to **6/6**. This is measured, not
assumed — see [`06-testing-and-evaluation.md`](06-testing-and-evaluation.md).

**Scaling boundary.** Every chunk vector is loaded and scored per query. That is fine to
roughly 5,000 chunks. Beyond that, move to pgvector with an HNSW index; only
`services/rag.py` changes.

---

## 2.6 Provider abstraction

Four families, one pattern each: an abstract base, concrete implementations, and a
cached factory that degrades gracefully.

| Family | Base | Implementations | Default |
|---|---|---|---|
| LLM | `BaseLLMProvider` | `AnthropicProvider`, `MockProvider` | auto |
| STT | `BaseSTT` | Browser, Whisper, Deepgram, Mock | browser |
| TTS | `BaseTTS` | Browser, ElevenLabs, pyttsx3, Mock | browser |
| Embeddings | `BaseEmbedder` | Hashing, SentenceTransformer | hashing |

Every factory catches construction failure and falls back rather than crashing:

```python
try:
    return WhisperSTT()
except Exception as exc:
    log.warning("STT provider %s unavailable (%s) - using browser mode.", provider, exc)
    return BrowserSTT()
```

A missing optional dependency degrades the deployment; it never takes it down.

### The offline planner

`MockProvider` is not a language model. It is a rule-based planner that speaks the
**same tool-calling protocol** as Claude: it emits `ToolUse` objects, receives
`tool_result` blocks back, and renders the results into prose. That single design choice
is what lets the entire system — agent loop, tool execution, citations, escalation,
voice, analytics — be demonstrated and tested with no API key, no cost and no network.

It routes by weighted pattern matching, with policy questions deliberately ordered
*before* action verbs so "what is your refund **policy**" reaches the knowledge base
rather than starting a refund.

---

## 2.7 Guardrails

Guardrails run **around** the model, not inside the prompt, because prompt instructions
can be argued away and code cannot.

| Stage | Checks | On trigger |
|---|---|---|
| **Input** | Prompt-injection patterns | Log a warning, continue |
| | Legal threat, fraud, injury, self-harm, media escalation | **Force** escalation to a human |
| | Credential mentions (CVV, OTP, PIN) | Flag; the prompt already forbids requesting them |
| **Output** | API keys, bearer tokens, database DSNs | Redact from the reply |
| | Meta-disclosure ("my system prompt says…") | Flag |
| | Empty response | Replace with the fallback message |
| **Post-turn** | Sentiment ≤ −0.55 | Escalate |
| | Explicit human request | Escalate |
| | ≥ 2 tool errors | Escalate |
| | ≥ 8 turns unresolved and negative | Escalate |
| | Gold/Platinum tier, negative, ≥ 4 turns | Escalate early |

The post-turn rules are the important ones: **the model does not get a vote.** A
customer who is clearly upset gets a human whether or not the LLM decided to call
`escalate_to_human`.

---

## 2.8 Design decisions and trade-offs

| Decision | Alternative | Why this way | Cost accepted |
|---|---|---|---|
| Tool calling for all facts | Fine-tuning on support transcripts | Grounded, auditable, updates instantly when data changes | Extra round-trips per turn |
| Local NLU before the LLM | Ask the LLM to classify | Routing and escalation never depend on a network call; analytics work offline | Rule-based classifiers are less nuanced |
| Rule-based escalation | Trust the model's tool call | A model can be talked out of escalating; rules cannot | Occasional false-positive handoff |
| Offline planner as a first-class provider | Require an API key | Zero-cost demo, deterministic tests, no network in CI | The planner does not paraphrase |
| Async SQLAlchemy | Sync + threadpool | One concurrency model across REST and WebSocket | Async ORM pitfalls (lazy loading) |
| JSON-array embeddings | pgvector from day one | Runs on SQLite with no server | Full scan per query; ~5k chunk ceiling |
| Browser speech by default | Server-side Whisper | No keys, no downloads, no audio round-trip, better privacy | Chrome/Edge/Safari only |
| String columns for enums | Native DB enums | Adding a value needs no migration | No DB-level constraint |
| Prior turns replayed as plain text | Replay full tool blocks | Small, stable context window | The model cannot re-read old tool payloads |

### Two decisions worth expanding

**Why prior turns are not replayed with their tool traffic.** Replaying every historical
`tool_use`/`tool_result` block would grow the context linearly with conversation length
and re-expose stale data (an order status that has since changed). Instead the last 12
turns are replayed as plain text and the agent re-calls tools when it needs current
facts. The cost is that the model cannot re-read an old tool payload; the benefit is
that it can never quote a stale one.

**Why tools return errors as data.** Every handler catches its own exceptions and
returns `{"error": ...}`. A tool failure therefore becomes something the model can see
and recover from — apologise, try a different approach, or escalate — rather than a 500
that loses the turn. Two such failures in one conversation trip the escalation rule.

---

## 2.9 Security model

| Layer | Control |
|---|---|
| Transport | HTTPS/WSS in production (nginx terminates) |
| Authentication | JWT access (12 h) + refresh (14 d), bcrypt cost 12 |
| Authorisation | Role guards on staff endpoints; per-record ownership on orders, tickets and conversations |
| WebSocket auth | Token as a query parameter (browsers cannot set WS headers), validated on connect |
| Input | Pydantic validation, 12 MB audio cap, prompt-injection screening |
| Data at rest | PII regex-redacted **before** the first write; card numbers, OTPs and CVVs never stored |
| Output | Secret patterns stripped from every reply |
| Audit | `tool_call_logs` records every automated action with arguments and result |
| Errors | Domain exceptions → typed JSON; unhandled exceptions logged server-side and returned as a generic 500 |

**Known demo relaxation:** `ALLOW_ANONYMOUS_ORDER_LOOKUP=true` lets a signed-out visitor
look up an order by number, so the storefront demo is usable without an account. It is
documented as demo-only and must be `false` in production.

---

## 2.10 Frontend architecture

```
main.tsx ─▶ BrowserRouter ─▶ App (route table + auth guards)
                                │
                          AppShell (role-aware nav, runtime badge)
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   Customer pages         Staff console            ChatPanel
   storefront             conversations            ├ MessageBubble
   support                tickets                  │  ├ tool trace
   my orders              knowledge admin          │  └ citations
   help centre            analytics                └ VoiceCall (WS)
                                │
                     zustand stores: auth · chat
                     lib: api.ts · speech.ts · utils.ts
```

State is deliberately minimal: two Zustand stores and component-local `useState`. There
is no data-fetching library — each page owns its load effect, which keeps the data flow
readable at this size.

The **runtime badge** in the sidebar reads `GET /capabilities` and shows which LLM,
speech and embedding providers the running deployment actually uses. It exists because
"which mode is this running in?" is the first question anyone asks when demonstrating
the project.

---

## 2.11 Extension points

| To add | Touch only |
|---|---|
| A new LLM provider | `services/llm/`: subclass `BaseLLMProvider`, register in the factory |
| A new agent capability | `agent/tools.py`: one `@tool`-decorated async function |
| A new channel (SMS, Instagram) | Add to `ChannelType`; the orchestrator is channel-agnostic |
| A real ERP / OMS | Reimplement `services/orders_service.py` against the real API |
| pgvector | `services/rag.py` only — the column type and the search query |
| A new guardrail | `agent/policy.py`: add a pattern or a rule |
