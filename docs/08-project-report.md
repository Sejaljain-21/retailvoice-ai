# 8 · Project report

**RetailVoice AI — An AI Customer Support and Voice Agent for E-commerce and Retail**

---

## Abstract

Retail customer support is dominated by a small set of repetitive, data-lookup
questions — order status, returns, refund timelines, stock availability. Large language
models are fluent enough to handle these conversations but are structurally unsuited to
answering them, because they have no access to the customer's actual order and will
confidently produce a plausible refund window instead of the correct one.

This project builds a complete customer-support and voice agent for the e-commerce and
retail segment on one architectural commitment: **the language model is the interface to
facts, never the source of them.** Thirteen typed tools sit between the model and the
systems of record, so every claim about an order, a price or a policy traces back to a
logged tool call. Deterministic guardrails and escalation rules run outside the model,
so safety-critical decisions cannot be argued away by a persuasive prompt.

The system comprises an asynchronous FastAPI backend (16 tables, 60 REST endpoints, a
streaming voice WebSocket) and a React frontend (storefront widget, support page,
agent console, ticket queue, knowledge-base admin, analytics dashboard). It is validated
by 91 automated tests and a purpose-built evaluation harness measuring retrieval quality
(Precision@1 80.0 %, Recall@3 100 %, MRR 0.900) and agent behaviour (10/10 cases).
Against seeded traffic representative of retail support, the agent contains 75 % of
conversations without human involvement at an average CSAT of 4.0/5.

A deliberate design choice — a rule-based planner that speaks the same tool-calling
protocol as the LLM — allows the entire system to be demonstrated, tested and evaluated
with no API keys, no model downloads and no network access.

---

## 1 Introduction

### 1.1 Motivation

Support volume in e-commerce concentrates heavily in a few intents. In this project's
seeded traffic, drawn from realistic retail scenarios, order tracking, returns/refunds
and delivery delays account for a majority of conversations. Each is trivially
answerable *if* the answering system can read the order record, the courier scan and the
current policy — and unanswerable without that access, no matter how capable the
language model.

The three existing approaches each fail differently:

- **Human agents** are accurate but expensive, queue at peak, and cannot be available
  continuously.
- **Scripted chatbots and IVR** are cheap but cannot see customer data and dead-end on
  anything off-script.
- **Naive LLM chatbots** are fluent but ungrounded. This is the most dangerous failure,
  because an invented refund timeline is indistinguishable from a real one and the
  customer acts on it.

### 1.2 Problem statement

Build a customer-support agent for e-commerce and retail that handles chat and voice,
resolves routine requests end to end including state-changing actions, never states an
unverified fact, escalates reliably to a human, and is measurable.

### 1.3 Objectives

| # | Objective | Result |
|---|---|---|
| O1 | Containment ≥ 70 % | **75 %** |
| O2 | Every factual claim tool-backed | Enforced by architecture; asserted by tests |
| O3 | Voice as a first-class channel | Streaming WebSocket with barge-in |
| O4 | Reliable escalation | Deterministic rules, model has no veto |
| O5 | Protect customer data | PII redacted pre-storage; ownership enforced |
| O6 | Measurable | 7 operational metrics + an evaluation harness |
| O7 | Zero external dependencies to run | Runs from a clean checkout with no keys |

### 1.4 Scope

**Included:** chat and voice across five channels; order lookup, tracking, cancellation
and returns; stock, recommendations, delivery estimates, store locator; policy answers
grounded in an editable knowledge base; ticketing with SLA; human handoff with
transcript; analytics.

**Excluded:** real payment capture, live courier APIs, ERP synchronisation, native
mobile applications, multi-tenancy.

---

## 2 Background

### 2.1 Retrieval-augmented generation

RAG (Lewis et al., 2020) grounds generation in retrieved documents. The standard
pipeline — chunk, embed, retrieve by vector similarity, inject into the prompt — is
adopted here for policy questions, with one departure: retrieval is **hybrid**, fusing
dense similarity with lexical coverage and a title-match signal. Section 5.2 shows this
was necessary rather than decorative — dense-only retrieval scored 56.7 % Precision@1
against the hybrid's 80.0 %.

### 2.2 Tool use / function calling

Modern LLM APIs expose structured tool calling: the model emits a typed request, the
application executes it, and the result is returned as a message. This project treats
tool calling as the *primary* grounding mechanism rather than a supplementary one. RAG
covers policy; tools cover everything transactional, which is the majority of retail
support.

### 2.3 Agent architectures

ReAct (Yao et al., 2022) established interleaved reasoning and acting. This project
implements a bounded ReAct-style loop — at most six tool iterations, after which the
turn escalates rather than continuing. The bound is a design decision, not a limitation:
an agent that cannot resolve a request in six tool calls has almost certainly
encountered something a human should see.

### 2.4 Guardrails

Prompt-level instructions are advisory. An instruction that says "never reveal your
system prompt" can be circumvented by a sufficiently creative user. This project
therefore places safety-critical logic in code that executes around the model — input
screening, output filtering, and escalation rules that run after the model has produced
its reply and can override it.

---

## 3 System design

### 3.1 Architecture

Layered, with the tool boundary as the central abstraction:

```
Client (React + Web Speech API)
    │ REST /api/v1        WS /ws/voice
    ▼
FastAPI  ─▶  Agent orchestrator
                 │
     ┌───────────┼───────────┬──────────────┐
     ▼           ▼           ▼              ▼
   NLU     LLM provider   13 tools     Guardrails
 (local)   Claude│mock    (grounded)   (deterministic)
                                │
                     ┌──────────┴──────────┐
                     ▼                     ▼
              SQLAlchemy (async)    Retrieval index
              SQLite / PostgreSQL   chunks + vectors
```

### 3.2 The agent loop

Eight stages per turn:

1. **NLU** — intent (16 classes), sentiment, language and PII detection, computed
   locally so routing never depends on a network call.
2. **Input guardrails** — prompt-injection screening; hard-escalation topics (legal,
   fraud, injury, self-harm) force a handoff immediately.
3. **Persist** the redacted turn with its annotations.
4. **RAG pre-fetch** for intents that are usually policy questions, removing a
   round-trip on the most common question type.
5. **LLM ⇄ tool loop**, bounded at six iterations, every call timed and logged.
6. **Output guardrails** — strip anything resembling a leaked secret; replace empty
   responses.
7. **Escalation rules** — evaluated independently of the model.
8. **Persist** the reply with citations, tool trace, token counts and latency.

### 3.3 Grounding

Three layers: the prompt states the rule; the tools are the only source of the facts;
and `tool_trace` plus `citations` are returned with every reply and rendered in the UI.
The third layer is what makes the first two verifiable — a reviewer can open any answer
and see exactly which tool produced which value.

### 3.4 Escalation

Escalation fires on any of: explicit request; sentiment ≤ −0.55; two or more tool
errors; eight turns unresolved with negative sentiment; a gold/platinum customer unhappy
after four turns; or a hard-escalation topic. Priority is derived from intent, sentiment
and customer tier; the full transcript is attached; the least-loaded agent is assigned.

**The model does not get a vote.** This is the single most important safety property in
the design: an upset customer is handed to a human whether or not the LLM chose to
escalate.

### 3.5 Voice

Two capture paths behind one WebSocket. By default the browser performs recognition and
synthesis, so **no audio leaves the device** and no keys are required; with
`STT_PROVIDER=whisper|deepgram`, MediaRecorder chunks are streamed to the server
instead. The voice system prompt caps replies at ~55 words and forbids markdown, and a
post-processing step expands currency symbols and strips residual formatting before
synthesis.

### 3.6 Provider abstraction

Four families (LLM, STT, TTS, embeddings), each an abstract base with several
implementations and a cached factory that degrades gracefully — a missing optional
dependency downgrades the deployment rather than taking it down.

The offline planner deserves specific mention. `MockProvider` is not a language model;
it is a rule-based planner that emits the same `ToolUse` structures, consumes the same
`tool_result` blocks, and renders results into prose. Because it speaks the same
protocol, the entire system is exercisable with no external dependency — which is what
makes the test suite deterministic and the evaluation harness runnable in CI.

---

## 4 Implementation

| Layer | Technology | Rationale |
|---|---|---|
| Backend | FastAPI, async SQLAlchemy 2.0, Pydantic v2 | Async throughout for REST + WebSocket; typed contracts |
| Database | SQLite / PostgreSQL | Zero-setup demo, production-ready path, no code change |
| LLM | Claude Sonnet 5 / offline planner | Strong tool calling; a zero-cost fallback |
| Speech | Web Speech API / Whisper / Deepgram / ElevenLabs | Privacy and cost by default; quality on demand |
| Retrieval | Custom hashing embedder + hybrid ranking | No model download; measured against alternatives |
| Frontend | React 18, TypeScript, Tailwind, Zustand, Recharts | Typed end to end; minimal state |
| Deployment | Docker Compose, nginx | Reproducible; correct WebSocket proxying |

**Scale:** ~11,600 lines across 106 files — 58 backend modules, 25 frontend modules, 91
tests, 8 documents.

### 4.1 Engineering decisions worth recording

**Prior turns are replayed as plain text, not as tool traffic.** Replaying historical
`tool_use`/`tool_result` blocks would grow the context linearly and re-expose stale data
— an order status that has since changed. The last 12 turns are replayed as text and the
agent re-calls tools for current facts. It cannot re-read an old tool payload; it also
cannot quote a stale one.

**Tools return errors as data.** Every handler catches its own exceptions and returns
`{"error": …}`, so a tool failure becomes something the model can see and recover from
rather than a 500 that loses the turn. Two failures in a conversation trip the
escalation rule.

**Tool results carry two message fields.** `message` is customer-safe; `agent_hint`
carries the internal instruction. This split came from an observed defect: an early
version returned *"Ask the customer to re-read the order number"* as the only field, and
the offline planner repeated that instruction verbatim to the customer.

---

## 5 Results

### 5.1 Functional completeness

All nine functional requirement groups implemented. All eight acceptance criteria met
(see §1.9 of the SRS).

### 5.2 Retrieval evaluation

30 labelled support questions, phrased as customers phrase them rather than in the
articles' own wording:

```
Precision@1    80.0 %
Recall@3      100.0 %
MRR            0.900
p50 latency   30.8 ms
```

**Ablation study:**

| Configuration | P@1 | R@3 | MRR |
|---|---:|---:|---:|
| **Full hybrid (shipped)** | **80.0 %** | **100.0 %** | **0.900** |
| − no title boost | 70.0 % | 93.3 % | 0.806 |
| − no stemming | 76.7 % | 90.0 % | 0.828 |
| − with chunk-level IDF | 76.7 % | 100.0 % | 0.878 |
| − with document-level IDF | 76.7 % | 100.0 % | 0.883 |
| Dense (vector) only | 56.7 % | 86.7 % | 0.711 |
| Lexical only | 80.0 % | 96.7 % | 0.867 |

Four findings:

1. **Dense-only retrieval is the weakest configuration.** With a dependency-free hashing
   embedder, pure vector similarity is noisy on short queries. This is the strongest
   argument for hybrid search in this project.
2. **Stemming is load-bearing** — removing it costs 10 points of Recall@3, meaning the
   correct article leaves the model's context entirely for three questions. Support
   queries and help articles disagree constantly on word form.
3. **The title boost earns its weight**, contributing 10 points of Precision@1.
4. **IDF weighting made results slightly worse and was disabled.** This was the
   surprise. The implementation is correct and IDF is the textbook choice, but with 14
   documents there is nothing to estimate — nearly every content term is "rare", so the
   weights amplify chunking accidents. It remains in the code as a documented flag, off
   by default, to be revisited at a few hundred articles.

A sweep across 20 combinations of the three fusion weights produced 80.0 % Precision@1
for *every* valid combination: the ceiling is the embedder, not the fusion. The six
remaining misses require semantics the hashing embedder cannot represent — connecting
"cannot be returned" to "non-returnable", for instance.

### 5.3 Agent behaviour

Ten end-to-end cases asserting behaviour rather than wording: **10/10 passed**, p50
latency 163 ms.

The set deliberately includes a negative case — an ordinary greeting must call no tools
and must not escalate. An agent that escalates everything would score perfectly on the
escalation cases and be useless in production.

### 5.4 Operational metrics

| Metric | Value |
|---|---|
| Conversations | 36 |
| Containment rate | **75.0 %** |
| Deflection rate | 75.0 % |
| Average CSAT | **4.00 / 5** |
| Average first response | 1.7 s |
| Escalation rate | 25 % |
| Tool success rate | 100 % |

Objective O1 (containment ≥ 70 %) is met. The figure is only as honest as the seed data;
the conversation scripts were written to span realistic support traffic including a
hostile complaint and an unresolvable delay, so 25 % escalation is the intended shape.

### 5.5 Test coverage

91 tests across five files, ~15 seconds, no network. Security properties are asserted
rather than assumed: cross-customer access is denied at both the API and tool layers,
staff endpoints reject customers, PII never reaches storage, and goodwill vouchers above
the policy limit are refused.

---

## 6 Discussion

### 6.1 What the architecture bought

Confining the LLM to *choosing* tools and *wording* results — never producing facts —
had effects beyond correctness:

- **Testability.** Behaviour became assertable. "Does an order question call an order
  tool?" is a test; "is the answer good?" is not.
- **Auditability.** `tool_call_logs` answers "why did the agent say that?" for every
  reply.
- **Substitutability.** Replacing Claude with a rule-based planner required no change
  to the orchestrator, the tools, or the frontend.
- **Instant policy updates.** Editing a knowledge-base article changes the agent's
  answers in the same request, because the answer was never in the weights.

### 6.2 What was harder than expected

**Async SQLAlchemy lazy loading.** Serialising a freshly created order triggered an
implicit lazy load of its `shipment` relationship outside an await boundary, producing a
`MissingGreenlet` error that surfaced as an opaque 500. The fix — re-reading through an
eager-loading query after mutation — is small; finding it was not. This class of bug is
the main cost of the async ORM.

**Retrieval quality on short queries.** The first implementation was pure cosine
similarity over hashing embeddings and retrieved the wrong article for half the
benchmark questions. Fixing it required measuring rather than guessing: a stemmer, a
title-match signal, and — as the ablation later showed — *not* the IDF weighting that
seemed most principled.

**Keeping internal text away from customers.** Tool results are written for the model,
but a weak model may echo them verbatim. Splitting every failure message into
customer-safe and agent-only fields was a direct response to observing that happen.

### 6.3 Limitations

- The offline planner is rule-based. It demonstrates the system faithfully but does not
  paraphrase or reason about novel situations.
- Browser speech recognition is Chrome/Edge/Safari only; Firefox needs server-side
  Whisper.
- The hashing embedder is lexically biased; six of thirty benchmark questions need
  genuine semantics.
- Embeddings are scored by full scan — fine to roughly 5,000 chunks, then pgvector.
- Payments, courier APIs and inventory sync are simulated.
- No load testing; throughput under concurrency is unmeasured.
- Response quality in Hindi and Hinglish is untested, though detection works.

### 6.4 Threats to validity

The containment and CSAT figures come from **seeded** conversations, not real users. The
scripts were written to be representative, but they were written by the same author as
the agent, which is a real bias. The retrieval benchmark is 30 questions — the 10-point
ablation gaps are meaningful; the 3.3-point IDF difference is one ranking position and
was treated as marginal rather than decisive.

---

## 7 Future work

**Near term**
- `sentence-transformers` embeddings to close the semantic gap in retrieval.
- Alembic migrations before any deployment holding real data.
- Prometheus metrics and OpenTelemetry tracing across the tool loop.
- Rate limiting at the ingress.

**Medium term**
- pgvector with an HNSW index.
- Prompt caching for the system prompt, which is large and identical across turns.
- Route trivial turns to a smaller model — the local NLU already identifies them.
- WhatsApp and email channel adapters; the data model already supports them.

**Research directions**
- **Learned escalation.** Replace hand-tuned thresholds with a classifier trained on
  resolved conversations and CSAT outcomes.
- **Retrieval feedback loop.** Use the `helpful_count` signal and unanswered questions
  to identify knowledge-base gaps automatically.
- **Proactive support.** The system already detects late shipments; contacting the
  customer before they contact support is a natural extension.
- **Multilingual evaluation.** Build a labelled Hindi/Hinglish set and measure, rather
  than assuming detection implies quality.

---

## 8 Conclusion

This project set out to build a customer-support agent for e-commerce and retail that is
useful without being untrustworthy. The central commitment — that the language model is
the interface to facts rather than their source — proved to be the decision everything
else followed from. It made behaviour testable, actions auditable, providers
substitutable, and policy updates instantaneous.

The system meets all seven objectives: 75 % containment against a 70 % target, 100 %
Recall@3 in retrieval, 10/10 on agent behaviour, and a full demonstration that runs from
a clean checkout with no API keys.

The most instructive result was a negative one. IDF weighting — the textbook choice,
correctly implemented, and the technique that seemed most principled — measurably
degraded retrieval at this corpus size and was turned off. It remains in the codebase as
a documented flag rather than deleted, because it is expected to win at scale. Shipping
it on by default because it *ought* to work would have been the easier decision and the
wrong one.

---

## References

1. Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP
   Tasks.* NeurIPS.
2. Yao, S. et al. (2022). *ReAct: Synergizing Reasoning and Acting in Language Models.*
   ICLR 2023.
3. Karpukhin, V. et al. (2020). *Dense Passage Retrieval for Open-Domain Question
   Answering.* EMNLP.
4. Robertson, S. & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and
   Beyond.* Foundations and Trends in Information Retrieval.
5. Radford, A. et al. (2022). *Robust Speech Recognition via Large-Scale Weak
   Supervision (Whisper).* OpenAI.
6. Anthropic (2024). *Building Effective Agents.* Engineering documentation.
7. Malkov, Y. & Yashunin, D. (2018). *Efficient and Robust Approximate Nearest Neighbor
   Search Using HNSW Graphs.* IEEE TPAMI.

---

## Appendix A — Repository map

```
backend/app/agent/       orchestrator, 13 tools, prompts, guardrail policy
backend/app/api/v1/      60 REST endpoints across 9 modules
backend/app/services/    LLM · speech · embeddings · RAG · NLU · domain services
backend/app/models/      16 SQLAlchemy tables
backend/app/ws/          voice WebSocket
backend/tests/           91 tests
backend/evaluate.py      retrieval + agent evaluation harness
frontend/src/pages/      8 pages
frontend/src/components/ chat panel, voice call, message bubble, UI kit
docs/                    8 documents
```

## Appendix B — Reproducing the results

```bash
git clone <repository> && cd "Customer Support and Voice Agent"
./scripts/dev.sh                                  # or .\scripts\dev.ps1

cd backend
../.venv/bin/python -m pytest                     # 91 tests
../.venv/bin/python -m app.db.seed --reset        # deterministic dataset
../.venv/bin/python evaluate.py                   # the numbers in §5.2–5.3
```

The seed uses a fixed RNG (`20250816`), so the dataset — and therefore every metric in
this report — is reproducible on any machine.
