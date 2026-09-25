"""The agent loop: one customer utterance in, one grounded reply out.

    NLU  ->  input guardrails  ->  persist turn  ->  pre-fetch RAG
         ->  LLM  <-> tool execution loop  ->  output guardrails
         ->  policy escalation  ->  persist reply + telemetry

Everything is instrumented (tokens, latency, tool traces, citations) because the
analytics dashboard and the evaluation harness read from those records.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import policy, prompts
from app.agent.tools import ToolContext, execute as execute_tool, tool_schemas
from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import (
    ChannelType,
    ConversationStatus,
    EscalationReason,
    Intent,
    MessageRole,
    Sentiment,
    TicketStatus,
)
from app.models.support import Conversation, Message, Ticket, ToolCallLog
from app.models.user import CustomerProfile, User
from app.services import nlu as nlu_service
from app.services import rag
from app.services.llm import ToolSpec, get_llm
from app.services.speech import to_speakable

log = get_logger(__name__)

HISTORY_TURNS = 12          # prior messages replayed into the model
EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]

# Intents where pre-fetching help-centre passages measurably improves grounding.
RAG_PREFETCH_INTENTS = {
    Intent.RETURN_REFUND,
    Intent.PRODUCT_INQUIRY,
    Intent.PAYMENT_ISSUE,
    Intent.OFFERS_DISCOUNTS,
    Intent.ACCOUNT_HELP,
    Intent.STORE_INFO,
    Intent.UNKNOWN,
}


@dataclass
class AgentTurn:
    conversation_id: str
    message_id: str
    reply: str
    intent: Intent = Intent.UNKNOWN
    intent_confidence: float = 0.0
    sentiment: Sentiment = Sentiment.NEUTRAL
    sentiment_score: float = 0.0
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    escalated: bool = False
    escalation_reason: str | None = None
    handoff_ticket_number: str | None = None
    suggested_replies: list[str] = field(default_factory=list)
    latency_ms: int = 0
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def speakable(self) -> str:
        return to_speakable(self.reply)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
async def _load_history(db: AsyncSession, conversation_id: str) -> list[dict[str, Any]]:
    """Prior turns as plain text blocks. Tool traffic is not replayed - the model
    gets a compact narrative instead, which keeps the context small and stable."""
    rows = (
        await db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT,
                                  MessageRole.HUMAN_AGENT]),
            )
            .order_by(Message.created_at.desc())
            .limit(HISTORY_TURNS)
        )
    ).scalars().all()

    history: list[dict[str, Any]] = []
    for msg in reversed(rows):
        role = "user" if msg.role == MessageRole.USER else "assistant"
        content = msg.content
        if msg.role == MessageRole.HUMAN_AGENT:
            content = f"(human agent) {content}"
        if not content.strip():
            continue
        # Collapse consecutive same-role turns; the API requires alternation.
        if history and history[-1]["role"] == role:
            history[-1]["content"][0]["text"] += f"\n{content}"
        else:
            history.append({"role": role, "content": [{"type": "text", "text": content}]})

    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


async def _open_ticket_count(db: AsyncSession, customer_id: str | None) -> int:
    if not customer_id:
        return 0
    count = (
        await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.customer_id == customer_id,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS,
                                   TicketStatus.WAITING_CUSTOMER]),
            )
        )
    ).scalar_one()
    return int(count)


def _format_passages(hits: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"[{i + 1}] {h['title']} ({h['category']}, relevance {h['score']:.2f})\n{h['snippet']}"
        for i, h in enumerate(hits)
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def run_turn(
    db: AsyncSession,
    *,
    conversation: Conversation,
    user: User | None,
    text: str,
    voice_mode: bool = False,
    audio_duration_ms: int | None = None,
    transcript_confidence: float | None = None,
    on_event: EventCallback | None = None,
) -> AgentTurn:
    started = time.perf_counter()

    async def emit(event: str, payload: dict[str, Any]) -> None:
        if on_event:
            try:
                await on_event(event, payload)
            except Exception:  # pragma: no cover - never let the UI break the turn
                log.debug("Event callback failed for %s", event, exc_info=True)

    # -- 1. Understand ------------------------------------------------------
    understanding = nlu_service.analyze(text)
    guard = policy.check_input(text, understanding)
    if guard.warnings:
        log.info("Guardrail warnings on conversation %s: %s", conversation.id, guard.warnings)

    # -- 2. Persist the customer turn --------------------------------------
    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=understanding.redacted_text,
        intent=understanding.intent.value,
        intent_confidence=understanding.intent_confidence,
        sentiment=understanding.sentiment.value,
        sentiment_score=understanding.sentiment_score,
        was_redacted=understanding.was_redacted,
        audio_duration_ms=audio_duration_ms,
        transcript_confidence=transcript_confidence,
    )
    db.add(user_message)

    conversation.message_count += 1
    conversation.last_sentiment = understanding.sentiment.value
    conversation.sentiment_score = understanding.sentiment_score
    if understanding.language != "en":
        conversation.language = understanding.language
    if (
        conversation.primary_intent in (Intent.UNKNOWN, Intent.SMALL_TALK)
        and understanding.intent != Intent.UNKNOWN
    ):
        conversation.primary_intent = understanding.intent.value
    if conversation.message_count == 1 or conversation.title == "New conversation":
        conversation.title = (text.strip()[:70] or "New conversation").replace("\n", " ")
    if audio_duration_ms:
        conversation.voice_seconds += audio_duration_ms / 1000
    await db.flush()

    await emit("thinking", {"intent": understanding.intent.value,
                            "sentiment": understanding.sentiment.value})

    # -- 3. Pre-fetch grounding passages -----------------------------------
    prefetched: list[dict[str, Any]] = []
    if understanding.intent in RAG_PREFETCH_INTENTS:
        prefetched = await rag.search(db, understanding.redacted_text, top_k=3)

    # -- 4. Build the prompt ------------------------------------------------
    profile = None
    if user:
        profile = (
            await db.execute(
                select(CustomerProfile).where(CustomerProfile.user_id == user.id)
            )
        ).scalars().first()

    system_prompt = prompts.build_system_prompt(
        user=user,
        profile=profile,
        conversation=conversation,
        nlu_intent=understanding.intent.value,
        nlu_sentiment=understanding.sentiment.value,
        sentiment_score=understanding.sentiment_score,
        voice_mode=voice_mode or conversation.channel == ChannelType.VOICE,
        open_tickets=await _open_ticket_count(db, conversation.customer_id),
        retrieved_context=_format_passages(prefetched),
    )

    messages = await _load_history(db, conversation.id)
    if not messages or messages[-1]["role"] != "user":
        messages.append(
            {"role": "user", "content": [{"type": "text", "text": understanding.redacted_text}]}
        )

    # -- 5. Model / tool loop ----------------------------------------------
    llm = get_llm()
    specs = [ToolSpec(**schema) for schema in tool_schemas()]
    ctx = ToolContext(
        db=db,
        conversation=conversation,
        user=user,
        language=understanding.language,
        sentiment_score=understanding.sentiment_score,
        intent=understanding.intent.value,
    )

    tool_trace: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    tokens_in = tokens_out = 0
    model_name = ""
    reply_text = ""
    tool_errors = 0

    for iteration in range(settings.AGENT_MAX_TOOL_ITERATIONS):
        result = await llm.complete(system=system_prompt, messages=messages, tools=specs)
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        model_name = result.model or llm.name

        if not result.wants_tools:
            reply_text = result.text
            break

        # Record the assistant turn exactly as the model produced it.
        assistant_blocks: list[dict[str, Any]] = []
        if result.text:
            assistant_blocks.append({"type": "text", "text": result.text})
        for call in result.tool_uses:
            block: dict[str, Any] = {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
            if call.extra_content:
                block["extra_content"] = call.extra_content
            assistant_blocks.append(block)
        messages.append({"role": "assistant", "content": assistant_blocks})

        tool_result_blocks: list[dict[str, Any]] = []
        for call in result.tool_uses:
            await emit("tool_call", {"tool": call.name, "arguments": call.input})
            t0 = time.perf_counter()
            payload = await execute_tool(ctx, call.name, call.input)
            duration = int((time.perf_counter() - t0) * 1000)
            failed = isinstance(payload, dict) and "error" in payload
            if failed:
                tool_errors += 1

            db.add(
                ToolCallLog(
                    conversation_id=conversation.id,
                    message_id=user_message.id,
                    tool_name=call.name,
                    arguments=call.input,
                    result=payload if isinstance(payload, dict) else {"value": payload},
                    success=not failed,
                    error=payload.get("error") if failed else None,
                    duration_ms=duration,
                )
            )
            trace_entry = {
                "tool": call.name,
                "arguments": call.input,
                "result": payload,
                "success": not failed,
                "duration_ms": duration,
                "error": payload.get("error") if failed else None,
            }
            tool_trace.append(trace_entry)
            await emit("tool_result", trace_entry)

            tool_result_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(payload, default=str)[:6000],
                    "is_error": failed,
                }
            )

        messages.append({"role": "user", "content": tool_result_blocks})
        await db.flush()
    else:
        log.warning(
            "Conversation %s hit the %d-iteration tool ceiling.",
            conversation.id, settings.AGENT_MAX_TOOL_ITERATIONS,
        )
        reply_text = (
            "This is taking me longer than it should. Let me bring in a human colleague "
            "so you get a proper answer."
        )
        ctx.flags["force_escalate"] = True

    citations = ctx.flags.get("citations", [])

    # -- 6. Output guardrails ----------------------------------------------
    out_guard = policy.check_output(reply_text)
    if not out_guard.allowed:
        reply_text = prompts.FALLBACK_REPLY
    elif out_guard.sanitized_text is not None:
        reply_text = out_guard.sanitized_text

    warnings = list(guard.warnings or []) + list(out_guard.warnings or [])

    # -- 7. Escalation ------------------------------------------------------
    escalated = bool(ctx.flags.get("escalated"))
    escalation_reason = ctx.flags.get("escalation_reason")
    ticket_number = ctx.flags.get("ticket_created")

    if not escalated:
        decision = policy.should_escalate(
            nlu=understanding,
            turn_count=conversation.message_count,
            tool_errors=tool_errors,
            customer_tier=profile.tier if profile else "standard",
            already_escalated=conversation.is_escalated,
            guardrail=guard,
        )
        if decision.should_escalate or ctx.flags.get("force_escalate"):
            from app.services import tickets_service

            reason = decision.reason or EscalationReason.REPEATED_FAILURE
            ticket = await tickets_service.escalate_conversation(
                db, conversation, reason=reason, summary=decision.note or reply_text[:400]
            )
            escalated = True
            escalation_reason = reason.value
            ticket_number = ticket.ticket_number
            handoff = policy.HANDOFF_MESSAGE.format(ticket_number=ticket.ticket_number)
            reply_text = f"{reply_text}\n\n{handoff}" if reply_text else handoff
            await emit("escalated", {"reason": reason.value,
                                     "ticket_number": ticket.ticket_number})

    # -- 8. Persist the reply ----------------------------------------------
    latency_ms = int((time.perf_counter() - started) * 1000)
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=reply_text,
        intent=understanding.intent.value,
        sentiment=understanding.sentiment.value,
        tool_calls=[
            {"tool": t["tool"], "arguments": t["arguments"], "success": t["success"],
             "duration_ms": t["duration_ms"]}
            for t in tool_trace
        ],
        citations=citations,
        latency_ms=latency_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=model_name,
    )
    db.add(assistant_message)

    conversation.message_count += 1
    conversation.total_tokens += tokens_in + tokens_out
    conversation.total_latency_ms += latency_ms
    if escalated:
        conversation.status = ConversationStatus.ESCALATED
    elif conversation.status == ConversationStatus.ACTIVE and _looks_resolved(reply_text, text):
        conversation.resolved_by_ai = True
    await db.flush()

    turn = AgentTurn(
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        reply=reply_text,
        intent=understanding.intent,
        intent_confidence=understanding.intent_confidence,
        sentiment=understanding.sentiment,
        sentiment_score=understanding.sentiment_score,
        citations=citations,
        tool_trace=tool_trace,
        escalated=escalated,
        escalation_reason=escalation_reason,
        handoff_ticket_number=ticket_number,
        suggested_replies=(
            ["Yes, connect me", "No, continue here"] if escalated
            else nlu_service.suggested_replies(understanding.intent)
        ),
        latency_ms=latency_ms,
        model=model_name,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        warnings=warnings,
    )

    await emit("reply", {"text": reply_text, "escalated": escalated,
                         "suggested_replies": turn.suggested_replies})
    log.info(
        "turn conversation=%s intent=%s sentiment=%+.2f tools=%d latency=%dms escalated=%s",
        conversation.id, understanding.intent.value, understanding.sentiment_score,
        len(tool_trace), latency_ms, escalated,
    )
    return turn


def _looks_resolved(reply: str, question: str) -> bool:
    """Heuristic containment signal used by the analytics dashboard."""
    closers = ("anything else", "happy to help", "glad i could", "have a great day")
    return any(c in reply.lower() for c in closers)


# ---------------------------------------------------------------------------
# Conversation lifecycle helpers
# ---------------------------------------------------------------------------
async def get_or_create_conversation(
    db: AsyncSession,
    *,
    conversation_id: str | None,
    user: User | None,
    channel: ChannelType = ChannelType.WEB_CHAT,
    language: str = "en",
    anonymous_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Conversation:
    if conversation_id:
        conversation = (
            await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        ).scalars().first()
        if conversation:
            # Claim an anonymous thread once the visitor signs in.
            if user and not conversation.customer_id:
                conversation.customer_id = user.id
                await db.flush()
            return conversation

    conversation = Conversation(
        customer_id=user.id if user else None,
        anonymous_key=anonymous_key,
        channel=channel,
        language=language,
        conversation_metadata=metadata or {},
    )
    db.add(conversation)
    await db.flush()
    log.info("Opened conversation %s on %s", conversation.id, channel)
    return conversation


async def close_conversation(db: AsyncSession, conversation: Conversation) -> None:
    if conversation.status == ConversationStatus.ACTIVE:
        conversation.status = (
            ConversationStatus.RESOLVED if conversation.message_count > 1
            else ConversationStatus.ABANDONED
        )
        conversation.resolved_at = datetime.now(timezone.utc)
        conversation.resolved_by_ai = not conversation.is_escalated
        await db.flush()
