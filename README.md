# RetailVoice 

**An AI customer-support and voice agent for e-commerce and retail.**

A complete, running system — FastAPI backend, React frontend, realtime voice — where
the agent answers questions about *real* orders, *real* stock and *real* policies by
calling tools against a live database and a retrieval index, never from model memory.

It runs with **no API keys and no external services**. An offline rule-based planner
speaks the same tool-calling protocol as Claude, so every feature — the agent loop,
tool execution, grounded citations, escalation, the voice pipeline, analytics — is
fully demonstrable out of the box. Add `ANTHROPIC_API_KEY` and the same code path runs
on Claude instead.

---

## Contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Demo accounts](#demo-accounts)
- [What to try first](#what-to-try-first)
- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)
- [Documentation](#documentation)

---

## What it does

### For the customer
- **Chat** from a floating storefront widget or a full support page.
- **Live voice calls** — speak, get spoken answers, interrupt mid-sentence.
- **Real actions**: track a parcel, cancel an order, start a return with an RMA and a
  booked pickup, check stock, find a store, get a delivery estimate for a pincode.
- **Cited answers** — every policy reply links to the help-centre article it came from.
- **A human on request**, at any point, with the full transcript handed over.

### For the support team
- **Agent console** — every conversation, escalations first, with the tool trace the
  AI used and a box to reply as a human.
- **Ticket queue** with priority, SLA countdown and one-click claim/resolve.
- **Knowledge-base admin** — edit an article and it is re-embedded immediately, so the
  agent's answers change the moment the policy does.
- **Analytics** — containment, deflection, CSAT, handle time, intent mix, sentiment
  distribution, per-tool success rate and latency, and estimated LLM spend.

### Under the hood
| Capability | How |
|---|---|
| Grounding | 13 typed tools over the live catalogue, orders and knowledge base |
| Retrieval | Paragraph-aware chunking → hybrid dense + IDF-weighted lexical + title boost |
| Understanding | Local intent (16 classes), sentiment, language detection, PII redaction |
| Safety | Prompt-injection detection, secret-leak filtering, forced escalation on legal / fraud / safety topics |
| Escalation | Deterministic rules that fire **even if the model never asks to escalate** |
| Observability | Every tool call, token count and latency persisted and charted |

---

## Quick start

**Prerequisites:** Python 3.11+ and Node 18+. Nothing else.

### One command

```bash
./scripts/dev.sh
```

```powershell
.\scripts\dev.ps1
```

That creates the virtual environment, installs both dependency sets, seeds the demo
database and starts both servers.

### Or manually

```bash
python -m venv .venv && ./.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload
```

```bash
npm --prefix frontend install && npm --prefix frontend run dev
```

| | |
|---|---|
| Web app | <http://localhost:5173> |
| API docs (Swagger) | <http://localhost:8000/docs> |
| Voice WebSocket | `ws://localhost:8000/ws/voice` |

The database is created and seeded automatically on first start.

### Or Docker

```bash
docker compose up --build
```

Frontend on <http://localhost:3000>, API on <http://localhost:8000>.

---

## Demo accounts

| Role | Email | Password | What you see |
|---|---|---|---|
| Customer | `customer@retailvoice.ai` | `Demo@1234` | Gold tier, live orders, returns |
| Support agent | `agent1@retailvoice.ai` | `Demo@1234` | Conversation queue, tickets |
| Admin | `admin@retailvoice.ai` | `Admin@123` | Everything, plus analytics and the KB |

The storefront and chat also work **signed out**.

---

## What to try first

1. **Grounded lookup** — sign in as the customer, open *Get support*, ask
   *"Where is my order?"*. Expand **1 action** under the reply to see the
   `track_shipment` call and its arguments. One seeded order is deliberately late, so
   the agent proactively offers a delay remedy.

2. **Cited policy answer** — ask *"How long does a UPI refund take?"*. Expand
   **sources** to see the retrieved passage and its relevance score.

3. **A real state change** — ask *"I want to return it, it arrived damaged"*. The agent
   validates the return window against the product's policy, issues an RMA and books a
   pickup. Check *My orders* — the return is there.

4. **Escalation you didn't ask for** — type an angry message. Sentiment crosses the
   threshold and the conversation is handed to a human with a ticket, *without* the
   model deciding to do it. Sign in as the admin to find it at the top of
   *Conversations*.

5. **Voice** — click the microphone in the chat header. Speak a question. Chrome, Edge
   or Safari; speech never leaves the device in the default configuration.

6. **Close the loop** — as the admin, edit a help article in *Knowledge base*, then ask
   the agent about it. The answer changes immediately.

---

## Architecture

```
  Browser
    │  React + TypeScript + Tailwind
    │  Web Speech API (on-device STT/TTS by default)
    │
    ├── REST  /api/v1/*  ──────────┐
    └── WS    /ws/voice  ──────────┤
                                   ▼
                          FastAPI application
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   NLU (local)              Agent orchestrator            Guardrails
   intent · sentiment    ┌──── tool-calling loop ────┐   input + output
   language · PII        │                           │   escalation rules
                         ▼                           ▼
                   LLM provider                 13 tools
                   Claude │ offline planner      orders · catalogue
                                                 knowledge · tickets
                                                        │
                                   ┌────────────────────┴───────────┐
                                   ▼                                ▼
                          SQLAlchemy (async)              Retrieval index
                          SQLite / PostgreSQL             chunks + embeddings
```

**One turn, end to end:**

1. NLU classifies intent, sentiment, language and redacts PII — locally, so routing
   never depends on a network call.
2. Input guardrails scan for injection attempts and hard-escalation topics.
3. The turn is persisted, then relevant help-centre passages are pre-fetched.
4. The LLM runs a tool-calling loop (max 6 iterations); every call is timed and logged.
5. Output guardrails strip anything that looks like a leaked secret.
6. Escalation rules run **independently of the model** and can hand off regardless.
7. The reply, its citations, tool trace, token counts and latency are all stored — which
   is what makes the analytics dashboard and the evaluation harness possible.

See [`docs/02-architecture.md`](docs/02-architecture.md) for the detailed view.

---

## Project layout

```
.
├── backend/
│   ├── app/
│   │   ├── agent/          orchestrator, 13 tools, prompts, guardrail policy
│   │   ├── api/v1/         auth, catalog, orders, chat, voice, tickets,
│   │   │                   knowledge, analytics, health
│   │   ├── core/           settings, security, logging, error handling
│   │   ├── db/             session, schema init, seed dataset
│   │   ├── models/         16 SQLAlchemy tables
│   │   ├── schemas/        Pydantic request/response contracts
│   │   ├── services/       LLM · speech · embeddings · RAG · NLU ·
│   │   │                   orders · tickets · analytics
│   │   └── ws/             voice WebSocket
│   └── tests/              91 tests
├── frontend/
│   └── src/
│       ├── components/     chat panel, voice call, message bubble, UI kit
│       ├── pages/          storefront, support, orders, help centre,
│       │                   console, tickets, knowledge, analytics
│       ├── lib/            API client, browser speech, formatting
│       └── store/          auth and chat state
├── docs/                   SRS, architecture, data model, API, agent design,
│                           testing & evaluation, deployment, project report
├── scripts/                dev.sh · dev.ps1
└── docker-compose.yml
```

---

## Configuration

Copy `.env.example` to `.env`. Every setting has a working default — an empty file is
valid.

The settings that change behaviour most:

| Variable | Default | Effect |
|---|---|---|
| `LLM_PROVIDER` | `auto` | `auto` uses Claude when `ANTHROPIC_API_KEY` is set, else the offline planner |
| `ANTHROPIC_API_KEY` | *(empty)* | Set it to run on Claude |
| `STT_PROVIDER` | `browser` | `browser` · `whisper` (local) · `deepgram` · `mock` |
| `TTS_PROVIDER` | `browser` | `browser` · `elevenlabs` · `pyttsx3` · `mock` |
| `EMBEDDING_PROVIDER` | `hashing` | `sentence-transformers` for better recall |
| `DATABASE_URL` | SQLite file | Point at PostgreSQL for production |
| `ESCALATION_SENTIMENT_THRESHOLD` | `-0.55` | How upset before a forced handoff |
| `ENABLE_PII_REDACTION` | `true` | Mask contact and card details before storage |
| `ALLOW_ANONYMOUS_ORDER_LOOKUP` | `true` | **Demo only** — turn off in production |

Heavier optional providers (local Whisper, offline TTS, sentence-transformers) live in
`backend/requirements-optional.txt`.

---

## Testing

```bash
cd backend && ../.venv/bin/python -m pytest
```

91 tests, ~15 seconds, no network access:

| File | Covers |
|---|---|
| `test_nlu.py` | Intent, sentiment (incl. negation), language, PII redaction |
| `test_rag.py` | Chunking, embedding properties, retrieval relevance |
| `test_tools.py` | All 13 tools, ownership checks, policy limits, error paths |
| `test_agent.py` | Tool selection, grounding, guardrails, escalation, voice turns |
| `test_api.py` | Auth, catalogue, orders, knowledge, analytics, tickets, RBAC |

Security-relevant behaviour is asserted, not assumed — a customer cannot read another
customer's order, staff-only endpoints reject customers, PII never reaches storage, and
goodwill vouchers above the policy limit are refused.

---

## Deployment

```bash
docker compose up --build                  # SQLite, zero configuration
docker compose --profile postgres up -d    # with PostgreSQL
```

Before exposing it publicly: set a real `SECRET_KEY`, set `APP_ENV=production` and
`DEBUG=false`, switch to PostgreSQL, and set `ALLOW_ANONYMOUS_ORDER_LOOKUP=false`.
Full checklist in [`docs/07-deployment.md`](docs/07-deployment.md).

---

## Documentation

| Document | Contents |
|---|---|
| [`01-requirements-srs.md`](docs/01-requirements-srs.md) | Scope, stakeholders, functional and non-functional requirements, use cases |
| [`02-architecture.md`](docs/02-architecture.md) | Component and sequence views, design decisions and their trade-offs |
| [`03-data-model.md`](docs/03-data-model.md) | ER diagram, all 16 tables, indexes, lifecycle states |
| [`04-api-reference.md`](docs/04-api-reference.md) | Every endpoint, the WebSocket protocol, error shapes |
| [`05-agent-design.md`](docs/05-agent-design.md) | Prompt structure, the 13 tools, guardrails, escalation policy |
| [`06-testing-and-evaluation.md`](docs/06-testing-and-evaluation.md) | Test strategy, metric definitions, retrieval evaluation, results |
| [`07-deployment.md`](docs/07-deployment.md) | Docker, environments, scaling, security checklist |
| [`08-project-report.md`](docs/08-project-report.md) | Academic write-up: problem, literature, methodology, results, future work |

---

## Honest limitations

- The offline planner is **rule-based, not a language model**. It routes and renders
  well enough to demonstrate the full system, but it does not paraphrase or reason.
  Set `ANTHROPIC_API_KEY` for genuine conversational quality.
- Browser speech recognition is Chrome/Edge/Safari only. Firefox users need
  `STT_PROVIDER=whisper`.
- The default `hashing` embedder is lexical-leaning. It handles this knowledge base
  well; a larger corpus wants `sentence-transformers` and pgvector.
- Payments, real courier APIs and live inventory sync are simulated.

---

## Licence

MIT — see [`LICENSE`](LICENSE).
