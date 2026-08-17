# 6 · Testing and evaluation

Two layers: a **test suite** that asserts correctness, and an **evaluation harness**
that measures quality. Both run offline and deterministically.

```bash
cd backend
../.venv/bin/python -m pytest      # 91 tests, ~15 s
../.venv/bin/python evaluate.py    # retrieval + agent behaviour
```

---

## 6.1 Test strategy

| Level | File | Count | What it protects |
|---|---|---|---|
| Unit | `test_nlu.py` | 20 | Intent, sentiment, language, PII redaction |
| Unit | `test_rag.py` | 8 | Chunking, embedding properties, retrieval relevance |
| Integration | `test_tools.py` | 18 | All 13 tools, ownership, policy limits, error paths |
| Integration | `test_agent.py` | 22 | Tool selection, grounding, guardrails, escalation, voice |
| End-to-end | `test_api.py` | 23 | Auth, catalogue, orders, knowledge, analytics, RBAC |
| | **Total** | **91** | |

**Determinism** is by construction: `LLM_PROVIDER=mock`, `STT/TTS=mock`, a fixed-seed
dataset, and no network access anywhere in the suite. The same commit produces the same
result on any machine, which is what makes the suite usable in CI.

The test database is separate and rebuilt once per session. Because each test gets its
own event loop, the engine uses `NullPool` under `APP_ENV=test` — a pooled connection
created in one loop and reused in another is a classic async-SQLAlchemy failure, and
this avoids it entirely rather than working around it.

---

## 6.2 What the tests actually assert

Coverage percentage is a weak signal. These are the properties that matter, and each is
pinned by a named test:

### Security and privacy

| Property | Test |
|---|---|
| A customer cannot read another customer's order | `test_cannot_read_someone_elses_order` |
| The same holds at the tool layer, not just the API | `test_customer_cannot_read_another_customers_order` |
| Staff-only endpoints reject customers | `test_analytics_requires_staff`, `test_kb_write_requires_staff` |
| Emails, phones and card numbers never reach storage | `test_pii_is_redacted_before_storage` |
| Order numbers survive redaction (the agent needs them) | `test_pii_redaction_preserves_order_numbers` |
| Leaked API keys are stripped from replies | `test_output_guardrail_redacts_secrets` |

### Grounding

| Property | Test |
|---|---|
| An order question calls an order tool | `test_order_question_calls_the_order_tool` |
| A stock question calls the catalogue | `test_stock_question_calls_the_catalogue` |
| A policy answer carries citations | `test_policy_question_is_grounded_in_the_knowledge_base` |
| Every tool has a usable schema and description | `test_every_tool_has_a_valid_schema` |

### Escalation

| Property | Test |
|---|---|
| An explicit request escalates | `test_explicit_human_request_escalates` |
| Severe anger escalates without being asked | `test_furious_customer_escalates` |
| A legal threat forces escalation | `test_legal_threat_forces_escalation` |
| Repeated tool failure escalates | `test_escalation_rules` |
| Escalation produces an assigned ticket | `test_escalation_creates_a_ticket_and_flags_the_conversation` |

### Business rules

| Property | Test |
|---|---|
| A delivered order cannot be cancelled | `test_cancel_refuses_a_delivered_order` |
| Goodwill vouchers above the limit are refused | `test_goodwill_coupon_respects_the_policy_limit` |
| Recommendations only surface in-stock items | `test_recommendations_only_return_stocked_items` |
| Coupons actually reduce the total | `test_coupon_reduces_the_total` |
| A tool failure returns data, never an exception | `test_unknown_tool_returns_data_not_an_exception` |

---

## 6.3 Retrieval evaluation

`evaluate.py` holds 30 labelled support questions — two to three per help article,
phrased the way customers actually phrase them, and deliberately *not* using the
articles' own wording.

### Metrics

| Metric | Definition | Why it matters here |
|---|---|---|
| **Precision@1** | Correct article ranked first | The agent quotes the top passage, so rank 1 is what the customer reads |
| **Recall@3** | Correct article anywhere in the top 3 | All three go into the model's context |
| **MRR** | Mean of 1/rank | Rewards ranking correctly, not just retrieving |

### Results — as shipped

```
Precision@1    80.0 %
Recall@3      100.0 %
MRR            0.900
p50 latency   30.8 ms
```

**Recall@3 of 100 % is the number that matters most.** The correct article reaches the
model's context for every one of the 30 questions. The six P@1 misses are ranking
errors, not retrieval failures — the right article is present, just second or third.

### Ablation study

Each component removed in turn, same 30 questions:

| Configuration | P@1 | R@3 | MRR |
|---|---:|---:|---:|
| **Full hybrid (shipped)** | **80.0 %** | **100.0 %** | **0.900** |
| − no title boost | 70.0 % | 93.3 % | 0.806 |
| − no stemming | 76.7 % | 90.0 % | 0.828 |
| − with chunk-level IDF | 76.7 % | 100.0 % | 0.878 |
| − with document-level IDF | 76.7 % | 100.0 % | 0.883 |
| Dense (vector) only | 56.7 % | 86.7 % | 0.711 |
| Lexical only | 80.0 % | 96.7 % | 0.867 |

Four findings, all measured rather than assumed:

**1. Dense-only retrieval is the weakest configuration (56.7 %).** With the
dependency-free hashing embedder, pure vector similarity is noisy on short queries. This
is the single strongest argument for hybrid search in this project.

**2. Stemming is load-bearing.** Removing it costs 10 points of Recall@3 — the correct
article disappears from context entirely for 3 of 30 questions. Support queries and help
articles disagree constantly on word form ("cancel" vs "cancelling", "ship" vs
"shipped"); without folding them together, *"can I cancel after shipping"* retrieved the
**coupons** article.

**3. The title boost earns its 15 % weight.** Removing it costs 10 points of P@1 and 6.7
of Recall@3. Help-article titles are unusually information-dense, so a title match is
strong evidence of topical fit.

**4. IDF weighting made things slightly worse, so it was turned off.** This was the
surprise. IDF is the textbook choice and the implementation is correct, but with 14
documents there is nothing for it to estimate — nearly every content term is "rare", so
the weights amplify chunking accidents rather than genuine term rarity. Uniform coverage
beat both chunk-level and document-level IDF on all three metrics. The code keeps
`USE_IDF_WEIGHTING` as a documented switch, off by default, to be revisited when the
corpus reaches a few hundred articles.

That last finding is worth stating plainly: **the more sophisticated technique lost.**
It is in the codebase as a flag rather than deleted, because it is expected to win at
scale — but shipping it on by default would have been cargo-culting a benchmark result
that says the opposite.

### Where retrieval still fails

The six P@1 misses share one cause: they need semantics the hashing embedder cannot
represent. *"What items cannot be returned"* has to connect "cannot be returned" to the
article's phrase "**non-returnable**", and no amount of lexical overlap gets there.

A weight sweep across 20 combinations of the three fusion weights produced **80.0 % P@1
for every valid combination** — the ceiling is the embedder, not the fusion. The
documented fix is `EMBEDDING_PROVIDER=sentence-transformers`, which replaces the
lexical-leaning embedder with a genuinely semantic one.

---

## 6.4 Agent behaviour evaluation

Ten end-to-end cases asserting behaviour rather than wording — wording changes when the
provider changes; behaviour must not.

```
[PASS] order status uses an order tool
[PASS] stock question hits the catalogue
[PASS] recommendation hits the catalogue
[PASS] policy answer is grounded and cited
[PASS] store question uses the locator
[PASS] explicit request escalates
[PASS] severe anger escalates without being asked
[PASS] legal threat escalates on the guardrail
[PASS] fraud report escalates
[PASS] ordinary greeting neither escalates nor calls tools

Pass rate   100.0 %  (10/10)
p50 latency 163.1 ms
```

The last case is the one people forget to write. An agent that escalates everything
scores perfectly on the escalation cases and is useless in production. Asserting that a
plain "Hi there" calls **no** tools and does **not** escalate pins the false-positive
side.

`evaluate.py` exits non-zero if Precision@1 drops below 70 % or the agent pass rate below
100 %, so it works as a CI quality gate.

---

## 6.5 Operational metrics

Definitions used by `/analytics/dashboard`, stated precisely because the headline claim
of the project depends on them:

| Metric | Definition |
|---|---|
| **Containment rate** | Conversations never escalated ÷ conversations with ≥ 2 messages |
| **Deflection rate** | Conversations that produced no ticket ÷ conversations with ≥ 2 messages |
| **CSAT** | Mean of 1–5 post-conversation ratings |
| **AHT** | Mean of (last message − first message) per conversation with ≥ 2 messages |
| **First response latency** | Mean `latency_ms` across assistant messages |
| **Tool success rate** | Successful calls ÷ total calls, per tool |
| **Estimated cost** | Tokens split 60/40 input/output at published Sonnet pricing |

The ≥ 2 message filter matters: a visitor who opens the widget and closes it should not
count as a contained conversation. Without that filter, containment inflates for free.

### Measured on the seeded dataset

| Metric | Value |
|---|---|
| Conversations | 36 |
| Containment rate | 75.0 % |
| Deflection rate | 75.0 % |
| Average CSAT | 4.00 / 5 |
| Average first response | 1.7 s |
| Escalated | 9 (25 %) |
| Tool success rate | 100 % across all tools |
| Voice minutes | 30.6 |

Against objective O1 (containment ≥ 70 %), the seeded traffic reaches **75 %**. That
figure is only as honest as the seed data: the scripts were written to span realistic
support traffic including a deliberately hostile complaint and an unresolvable delay, so
25 % escalation is the intended shape rather than an artefact.

---

## 6.6 Performance

Measured locally, offline provider, SQLite:

| Operation | p50 |
|---|---|
| Retrieval query (30 chunks) | 31 ms |
| Simple chat turn, no tools | 20 ms |
| Chat turn with one tool call | 163 ms |
| Tool execution (DB-backed) | 40–110 ms |
| Full test suite | 15 s |

With Claude Sonnet substituted, a tool-using turn runs roughly 1.5–3 s end to end,
dominated by the two model round-trips the tool loop requires.

---

## 6.7 Manual test checklist

Automated tests do not cover the browser speech path, since it depends on real
microphone permission and vendor APIs.

| # | Scenario | Expected |
|---|---|---|
| 1 | Widget opens on the storefront | Greeting appears |
| 2 | "Where is my order?" signed in | Tool trace shows `track_shipment` |
| 3 | Expand **sources** on a policy answer | Passage and relevance score |
| 4 | Start a return through chat | RMA appears in *My orders* |
| 5 | Angry message | Escalation banner and reference number |
| 6 | Voice call, Chrome | Orb pulses, transcript fills, reply is spoken |
| 7 | Interrupt mid-reply | Playback stops |
| 8 | Voice call, Firefox | Clear "browser not supported" guidance |
| 9 | Edit a KB article as admin, re-ask | Answer reflects the edit immediately |
| 10 | Sign in as agent | Escalated threads at the top of the queue |
| 11 | Claim and resolve a ticket | Status and assignee update |
| 12 | Analytics as admin | All panels populated |
| 13 | Keyboard-only navigation | Focus visible, all controls reachable |
| 14 | Mobile viewport | Sidebar collapses, chat usable |

---

## 6.8 Known gaps

Stated plainly rather than omitted:

- **No load testing.** Throughput under concurrency is unmeasured.
- **Voice E2E is manual.** Automating it needs a headless browser with a synthetic
  audio device.
- **The agent evaluation runs against the offline planner.** It asserts routing and
  escalation, which are provider-independent, but says nothing about the answer quality
  a real LLM would produce.
- **30 labelled retrieval questions is a small set.** A 1-question difference is one
  ranking position; the ablation gaps of 10 points are meaningful, the 3.3-point IDF gap
  is marginal and was treated as such.
- **No adversarial red-teaming** beyond the pattern-based injection tests.
- **Single-language evaluation.** Hindi and Hinglish detection work, but response
  quality in those languages is untested.
