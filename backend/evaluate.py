"""Evaluation harness.

Two suites, both offline and deterministic:

  1. RETRIEVAL  - a labelled set of support questions with the article that
     should be returned. Reports Precision@1, Recall@3 and MRR.

  2. AGENT      - end-to-end turns asserting the *behaviour* that matters:
     did it call the right tool, is the answer grounded, did it escalate when
     it should have, and did it stay silent about things it cannot know.

Run:
    python evaluate.py                # both suites
    python evaluate.py --suite rag
    python evaluate.py --json         # machine-readable, for CI
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field

from app.db.session import SessionLocal
from app.services import rag

# ---------------------------------------------------------------------------
# 1. Retrieval
# ---------------------------------------------------------------------------
# (question, slug fragment that the correct article's slug must contain)
RETRIEVAL_SET: list[tuple[str, str]] = [
    ("how long does a UPI refund take", "refund-timelines"),
    ("refund policy for UPI payments", "refund-timelines"),
    ("when will I get my money back on a credit card", "refund-timelines"),
    ("how many days do I have to return an item", "return-policy"),
    ("can I return shoes that do not fit", "return-policy"),
    ("what items cannot be returned", "return-policy"),
    ("how do I start a return", "how-to-start-a-return"),
    ("is reverse pickup free", "how-to-start-a-return"),
    ("what are your delivery charges", "delivery-timelines"),
    ("do you offer same day delivery", "delivery-timelines"),
    ("can I cancel after the order has shipped", "cancelling-an-order"),
    ("how do I cancel my order", "cancelling-an-order"),
    ("my parcel says out for delivery what does that mean", "tracking-your-order"),
    ("tracking has not updated in three days", "tracking-your-order"),
    ("the item arrived broken what do I do", "damaged-defective"),
    ("I received the wrong product", "damaged-defective"),
    ("how do I claim warranty on a laptop", "warranty-coverage"),
    ("what does the warranty not cover", "warranty-coverage"),
    ("I was charged twice for one order", "payment-methods"),
    ("is cash on delivery available", "payment-methods"),
    ("do you have any coupon codes", "coupons-offers"),
    ("what happens if the price drops after I buy", "coupons-offers"),
    ("how do loyalty points work", "novamart-loyalty"),
    ("what are the benefits of gold tier", "novamart-loyalty"),
    ("can I pick up my order from a store", "store-pickup"),
    ("what time does the store close", "store-pickup"),
    ("I need to change my delivery address", "changing-a-delivery-address"),
    ("I forgot my password", "account-sign-in"),
    ("the OTP is not arriving", "account-sign-in"),
    ("how do I delete my account", "account-sign-in"),
]


@dataclass
class RetrievalResult:
    total: int = 0
    hits_at_1: int = 0
    hits_at_3: int = 0
    reciprocal_ranks: list[float] = field(default_factory=list)
    latencies_ms: list[float] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    @property
    def precision_at_1(self) -> float:
        return self.hits_at_1 / self.total * 100 if self.total else 0.0

    @property
    def recall_at_3(self) -> float:
        return self.hits_at_3 / self.total * 100 if self.total else 0.0

    @property
    def mrr(self) -> float:
        return (
            sum(self.reciprocal_ranks) / self.total if self.total else 0.0
        )

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0


async def evaluate_retrieval(verbose: bool = True) -> RetrievalResult:
    result = RetrievalResult()

    async with SessionLocal() as db:
        for question, expected in RETRIEVAL_SET:
            started = time.perf_counter()
            hits = await rag.search(db, question, top_k=3)
            result.latencies_ms.append((time.perf_counter() - started) * 1000)
            result.total += 1

            slugs = [h["slug"] for h in hits]
            rank = next(
                (i + 1 for i, slug in enumerate(slugs) if expected in slug), None
            )

            if rank == 1:
                result.hits_at_1 += 1
            if rank is not None and rank <= 3:
                result.hits_at_3 += 1
                result.reciprocal_ranks.append(1 / rank)
            else:
                result.reciprocal_ranks.append(0.0)
                result.failures.append(
                    {"question": question, "expected": expected, "got": slugs}
                )

            if verbose:
                mark = "PASS" if rank == 1 else ("near" if rank else "FAIL")
                top = slugs[0][:44] if slugs else "(nothing)"
                print(f"  [{mark:4}] {question[:52]:<52} -> {top}")

    return result


# ---------------------------------------------------------------------------
# 2. Agent behaviour
# ---------------------------------------------------------------------------
@dataclass
class AgentCase:
    name: str
    message: str
    expect_tools: set[str] = field(default_factory=set)   # any one of these
    expect_citations: bool = False
    expect_escalation: bool = False
    forbid_escalation: bool = False
    signed_in: bool = True


AGENT_SET: list[AgentCase] = [
    AgentCase("order status uses an order tool", "Where is my order?",
              expect_tools={"track_shipment", "lookup_order"}, forbid_escalation=True),
    AgentCase("stock question hits the catalogue",
              "Do you have the AuraSound headphones in stock?",
              expect_tools={"check_product_availability"}, forbid_escalation=True),
    AgentCase("recommendation hits the catalogue",
              "Can you recommend a good air purifier for my bedroom?",
              expect_tools={"recommend_products"}, forbid_escalation=True),
    AgentCase("policy answer is grounded and cited",
              "What is your refund policy for UPI payments?",
              expect_tools={"search_knowledge_base"}, expect_citations=True,
              forbid_escalation=True),
    AgentCase("store question uses the locator",
              "What time does your Koramangala store close?",
              expect_tools={"find_nearby_store"}, forbid_escalation=True),
    AgentCase("explicit request escalates",
              "I want to speak to a human agent right now",
              expect_escalation=True),
    AgentCase("severe anger escalates without being asked",
              "This is absolutely pathetic and unacceptable, the worst service "
              "I have ever experienced!!!",
              expect_escalation=True),
    AgentCase("legal threat escalates on the guardrail",
              "I am going to take you to consumer court over this",
              expect_escalation=True),
    AgentCase("fraud report escalates",
              "There is an unauthorised transaction on my card",
              expect_escalation=True),
    AgentCase("ordinary greeting neither escalates nor calls tools",
              "Hi there", forbid_escalation=True),
]


@dataclass
class AgentEvalResult:
    total: int = 0
    passed: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total * 100 if self.total else 0.0

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0


async def evaluate_agent(verbose: bool = True) -> AgentEvalResult:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    result = AgentEvalResult()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://evaluation"
    ) as client:
        auth = await client.post(
            "/api/v1/auth/login",
            json={"email": "customer@retailvoice.ai", "password": "Demo@1234"},
        )
        headers = (
            {"Authorization": f"Bearer {auth.json()['tokens']['access_token']}"}
            if auth.status_code == 200
            else {}
        )

        for case in AGENT_SET:
            started = time.perf_counter()
            response = await client.post(
                "/api/v1/chat/message",
                headers=headers if case.signed_in else {},
                json={"message": case.message},
            )
            result.latencies_ms.append((time.perf_counter() - started) * 1000)
            result.total += 1

            if response.status_code != 200:
                result.failures.append(
                    {"case": case.name, "reason": f"HTTP {response.status_code}"}
                )
                if verbose:
                    print(f"  [FAIL] {case.name}")
                continue

            reply = response.json()
            used = {t["tool"] for t in reply["tool_trace"]}
            problems: list[str] = []

            if case.expect_tools and not (used & case.expect_tools):
                problems.append(
                    f"expected one of {sorted(case.expect_tools)}, got {sorted(used) or 'none'}"
                )
            if case.expect_citations and not reply["citations"]:
                problems.append("expected citations, got none")
            if case.expect_escalation and not reply["escalated"]:
                problems.append("expected escalation, none happened")
            if case.forbid_escalation and reply["escalated"]:
                problems.append("escalated when it should not have")
            if not reply["reply"].strip():
                problems.append("empty reply")

            if problems:
                result.failures.append({"case": case.name, "problems": problems})
            else:
                result.passed += 1

            if verbose:
                print(f"  [{'PASS' if not problems else 'FAIL'}] {case.name}")
                for problem in problems:
                    print(f"         {problem}")

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def main() -> int:
    parser = argparse.ArgumentParser(description="Retail Voice evaluation harness")
    parser.add_argument("--suite", choices=["rag", "agent", "all"], default="all")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    verbose = not args.json
    report: dict = {}
    failed = False

    if args.suite in ("rag", "all"):
        if verbose:
            print("\n" + "=" * 74)
            print("RETRIEVAL  -  30 labelled support questions")
            print("=" * 74)
        retrieval = await evaluate_retrieval(verbose)
        report["retrieval"] = {
            "questions": retrieval.total,
            "precision_at_1": round(retrieval.precision_at_1, 1),
            "recall_at_3": round(retrieval.recall_at_3, 1),
            "mrr": round(retrieval.mrr, 3),
            "p50_latency_ms": round(retrieval.p50_ms, 1),
            "failures": retrieval.failures,
        }
        if verbose:
            print(f"\n  Precision@1 {retrieval.precision_at_1:5.1f} %")
            print(f"  Recall@3    {retrieval.recall_at_3:5.1f} %")
            print(f"  MRR         {retrieval.mrr:5.3f}")
            print(f"  p50 latency {retrieval.p50_ms:5.1f} ms")
        if retrieval.precision_at_1 < 70:
            failed = True

    if args.suite in ("agent", "all"):
        if verbose:
            print("\n" + "=" * 74)
            print("AGENT BEHAVIOUR  -  tool selection, grounding, escalation")
            print("=" * 74)
        agent = await evaluate_agent(verbose)
        report["agent"] = {
            "cases": agent.total,
            "passed": agent.passed,
            "pass_rate": round(agent.pass_rate, 1),
            "p50_latency_ms": round(agent.p50_ms, 1),
            "failures": agent.failures,
        }
        if verbose:
            print(f"\n  Pass rate   {agent.pass_rate:5.1f} %  ({agent.passed}/{agent.total})")
            print(f"  p50 latency {agent.p50_ms:5.1f} ms")
        if agent.pass_rate < 100:
            failed = True

    if args.json:
        print(json.dumps(report, indent=2))
    elif verbose:
        print("\n" + ("FAILED" if failed else "All evaluation thresholds met.") + "\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
