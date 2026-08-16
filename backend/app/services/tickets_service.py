"""Ticketing, escalation and CSAT helpers."""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    ConversationStatus,
    EscalationReason,
    Intent,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.support import Conversation, Message, Ticket
from app.models.user import CustomerProfile, User

# Response-time commitments per priority, in hours.
SLA_HOURS: dict[str, int] = {
    TicketPriority.URGENT: 2,
    TicketPriority.HIGH: 8,
    TicketPriority.MEDIUM: 24,
    TicketPriority.LOW: 72,
}

# Intents that always deserve a faster lane.
HIGH_PRIORITY_INTENTS = {
    Intent.COMPLAINT,
    Intent.PAYMENT_ISSUE,
    Intent.DELIVERY_DELAY,
    Intent.HUMAN_HANDOFF,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_ticket_number() -> str:
    return f"TKT-{_now():%y%m%d}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=5))}"


def derive_priority(intent: str, sentiment_score: float, customer_tier: str = "standard") -> str:
    score = 0
    if intent in HIGH_PRIORITY_INTENTS:
        score += 2
    if sentiment_score <= -0.55:
        score += 2
    elif sentiment_score <= -0.2:
        score += 1
    if customer_tier in ("gold", "platinum"):
        score += 1

    if score >= 4:
        return TicketPriority.URGENT
    if score >= 2:
        return TicketPriority.HIGH
    if score >= 1:
        return TicketPriority.MEDIUM
    return TicketPriority.LOW


async def create_ticket(
    db: AsyncSession,
    *,
    subject: str,
    description: str = "",
    category: str = Intent.UNKNOWN.value,
    priority: str = TicketPriority.MEDIUM,
    customer_id: str | None = None,
    conversation_id: str | None = None,
    order_id: str | None = None,
    tags: list[str] | None = None,
    created_by_agent: bool = False,
) -> Ticket:
    ticket = Ticket(
        ticket_number=generate_ticket_number(),
        subject=subject[:240],
        description=description,
        category=category,
        priority=priority,
        customer_id=customer_id,
        conversation_id=conversation_id,
        order_id=order_id,
        tags=tags or [],
        created_by_agent=created_by_agent,
        sla_due_at=_now() + timedelta(hours=SLA_HOURS.get(priority, 24)),
    )
    db.add(ticket)
    await db.flush()
    return ticket


async def pick_available_agent(db: AsyncSession) -> User | None:
    """Least-loaded routing across active human agents."""
    agents = (
        await db.execute(
            select(User).where(
                User.role.in_([UserRole.AGENT, UserRole.SUPERVISOR]),
                User.is_active.is_(True),
            )
        )
    ).scalars().all()
    if not agents:
        return None

    loads: dict[str, int] = {}
    for agent in agents:
        count = (
            await db.execute(
                select(func.count(Ticket.id)).where(
                    Ticket.assigned_agent_id == agent.id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
                )
            )
        ).scalar_one()
        loads[agent.id] = int(count)

    return min(agents, key=lambda a: loads.get(a.id, 0))


async def queue_depth(db: AsyncSession) -> int:
    count = (
        await db.execute(
            select(func.count(Ticket.id)).where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
                Ticket.created_by_agent.is_(True),
            )
        )
    ).scalar_one()
    return int(count)


async def escalate_conversation(
    db: AsyncSession,
    conversation: Conversation,
    *,
    reason: EscalationReason,
    summary: str = "",
) -> Ticket:
    """Flag the thread, open a ticket and assign the least-busy human agent."""
    conversation.is_escalated = True
    conversation.status = ConversationStatus.ESCALATED
    conversation.escalated_at = _now()
    conversation.escalation_reason = reason.value

    tier = "standard"
    if conversation.customer_id:
        profile = (
            await db.execute(
                select(CustomerProfile).where(CustomerProfile.user_id == conversation.customer_id)
            )
        ).scalars().first()
        if profile:
            tier = profile.tier

    priority = derive_priority(
        conversation.primary_intent, conversation.sentiment_score, tier
    )

    transcript = await build_transcript(db, conversation.id, limit=40)
    ticket = await create_ticket(
        db,
        subject=f"[Escalated] {conversation.title}"[:240],
        description=(
            f"Escalation reason: {reason.value}\n"
            f"Detected intent: {conversation.primary_intent}\n"
            f"Sentiment: {conversation.last_sentiment} ({conversation.sentiment_score})\n"
            f"Channel: {conversation.channel}\n\n"
            f"Agent summary: {summary or 'n/a'}\n\n"
            f"--- Transcript ---\n{transcript}"
        ),
        category=conversation.primary_intent,
        priority=priority,
        customer_id=conversation.customer_id,
        conversation_id=conversation.id,
        tags=["escalation", reason.value, conversation.channel],
        created_by_agent=True,
    )

    agent = await pick_available_agent(db)
    if agent:
        ticket.assigned_agent_id = agent.id
        conversation.assigned_agent_id = agent.id

    await db.flush()
    return ticket


async def build_transcript(db: AsyncSession, conversation_id: str, limit: int = 40) -> str:
    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .limit(limit)
        )
    ).scalars().all()
    speaker = {"user": "Customer", "assistant": "AI Agent", "human_agent": "Human Agent"}
    return "\n".join(
        f"[{m.created_at:%H:%M}] {speaker.get(m.role, m.role.title())}: {m.content}"
        for m in rows
        if m.role != "system"
    )


async def resolve_conversation(
    db: AsyncSession, conversation: Conversation, *, by_ai: bool = True
) -> None:
    conversation.status = ConversationStatus.RESOLVED
    conversation.resolved_at = _now()
    conversation.resolved_by_ai = by_ai and not conversation.is_escalated
    await db.flush()
