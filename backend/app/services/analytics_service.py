"""Aggregations behind the operations dashboard.

Metric definitions (documented because they are what the project is evaluated on):

* **Containment rate** - conversations closed without ever being escalated,
  as a share of all conversations with at least one customer turn. This is the
  headline "did the AI handle it" number.
* **Deflection rate** - conversations that never produced a ticket.
* **CSAT** - mean of 1-5 post-conversation ratings.
* **AHT** (average handle time) - wall-clock seconds from first to last message.
* **First response time** - latency of the agent's first reply in a thread.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ConversationStatus, TicketStatus
from app.models.knowledge import KBDocument
from app.models.support import Conversation, Feedback, Message, Ticket, ToolCallLog

# Blended Claude Sonnet pricing, USD per million tokens, for cost estimation.
COST_PER_M_INPUT = 3.0
COST_PER_M_OUTPUT = 15.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _scalar(db: AsyncSession, stmt) -> float:
    value = (await db.execute(stmt)).scalar()
    return float(value or 0)


async def kpi_summary(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    since = _now() - timedelta(days=days)
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)

    total = int(await _scalar(db, select(func.count(Conversation.id))))
    in_window = int(
        await _scalar(db, select(func.count(Conversation.id)).where(Conversation.created_at >= since))
    )
    today_count = int(
        await _scalar(db, select(func.count(Conversation.id)).where(Conversation.created_at >= today))
    )
    active = int(
        await _scalar(
            db,
            select(func.count(Conversation.id)).where(
                Conversation.status == ConversationStatus.ACTIVE
            ),
        )
    )
    escalated = int(
        await _scalar(
            db, select(func.count(Conversation.id)).where(Conversation.is_escalated.is_(True))
        )
    )
    ai_resolved = int(
        await _scalar(
            db,
            select(func.count(Conversation.id)).where(
                Conversation.is_escalated.is_(False),
                Conversation.message_count >= 2,
            ),
        )
    )
    engaged = int(
        await _scalar(
            db, select(func.count(Conversation.id)).where(Conversation.message_count >= 2)
        )
    )

    ticketed = int(
        await _scalar(
            db,
            select(func.count(func.distinct(Ticket.conversation_id))).where(
                Ticket.conversation_id.is_not(None)
            ),
        )
    )

    csat_avg = await _scalar(db, select(func.avg(Feedback.rating)))
    csat_n = int(await _scalar(db, select(func.count(Feedback.id))))

    tokens = int(await _scalar(db, select(func.sum(Conversation.total_tokens))))
    voice_seconds = await _scalar(db, select(func.sum(Conversation.voice_seconds)))
    open_tickets = int(
        await _scalar(
            db,
            select(func.count(Ticket.id)).where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            ),
        )
    )

    # Average handle time: last message minus first, per conversation.
    spans = (
        await db.execute(
            select(
                Message.conversation_id,
                func.min(Message.created_at),
                func.max(Message.created_at),
                func.count(Message.id),
            ).group_by(Message.conversation_id)
        )
    ).all()
    durations = [
        (last - first).total_seconds()
        for _, first, last, count in spans
        if count >= 2 and first and last
    ]
    aht = sum(durations) / len(durations) if durations else 0.0

    first_response = await _scalar(
        db, select(func.avg(Message.latency_ms)).where(Message.latency_ms.is_not(None))
    )

    # Rough 60/40 input/output split for the cost estimate.
    cost = (tokens * 0.6 / 1_000_000 * COST_PER_M_INPUT) + (
        tokens * 0.4 / 1_000_000 * COST_PER_M_OUTPUT
    )

    return {
        "total_conversations": total,
        "conversations_window": in_window,
        "conversations_today": today_count,
        "active_conversations": active,
        "ai_resolved": ai_resolved,
        "escalated": escalated,
        "containment_rate": round(ai_resolved / engaged * 100, 1) if engaged else 0.0,
        "deflection_rate": round((engaged - ticketed) / engaged * 100, 1) if engaged else 0.0,
        "avg_csat": round(csat_avg, 2),
        "csat_responses": csat_n,
        "avg_handle_time_s": round(aht, 1),
        "avg_first_response_ms": round(first_response, 1),
        "open_tickets": open_tickets,
        "total_voice_minutes": round(voice_seconds / 60, 1),
        "total_tokens": tokens,
        "estimated_cost_usd": round(cost, 4),
    }


async def intent_breakdown(db: AsyncSession, limit: int = 12) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                Conversation.primary_intent,
                func.count(Conversation.id),
                func.avg(Conversation.sentiment_score),
            ).group_by(Conversation.primary_intent)
        )
    ).all()

    # Counted separately because SUM(CAST(bool)) is not portable across backends.
    escalations = dict(
        (
            await db.execute(
                select(Conversation.primary_intent, func.count(Conversation.id))
                .where(Conversation.is_escalated.is_(True))
                .group_by(Conversation.primary_intent)
            )
        ).all()
    )

    total = sum(int(count) for _, count, _ in rows) or 1
    out = []
    for intent, count, avg_sentiment in rows:
        count = int(count)
        esc = int(escalations.get(intent, 0))
        out.append(
            {
                "intent": intent or "unknown",
                "count": count,
                "percentage": round(count / total * 100, 1),
                "avg_sentiment": round(float(avg_sentiment or 0), 3),
                "escalation_rate": round(esc / count * 100, 1) if count else 0.0,
            }
        )
    out.sort(key=lambda d: d["count"], reverse=True)
    return out[:limit]


async def channel_breakdown(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Conversation.channel, func.count(Conversation.id)).group_by(Conversation.channel)
        )
    ).all()
    escalated = dict(
        (
            await db.execute(
                select(Conversation.channel, func.count(Conversation.id))
                .where(Conversation.is_escalated.is_(True))
                .group_by(Conversation.channel)
            )
        ).all()
    )
    total = sum(int(c) for _, c in rows) or 1
    return [
        {
            "channel": channel,
            "count": int(count),
            "percentage": round(int(count) / total * 100, 1),
            "containment_rate": round(
                (int(count) - int(escalated.get(channel, 0))) / int(count) * 100, 1
            ) if int(count) else 0.0,
        }
        for channel, count in rows
    ]


async def timeseries(db: AsyncSession, days: int = 14) -> list[dict[str, Any]]:
    since = _now() - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                Conversation.created_at,
                Conversation.is_escalated,
                Conversation.sentiment_score,
                Conversation.message_count,
            ).where(Conversation.created_at >= since)
        )
    ).all()

    buckets: dict[str, dict[str, Any]] = {}
    for i in range(days, -1, -1):
        key = (_now() - timedelta(days=i)).date().isoformat()
        buckets[key] = {"date": key, "conversations": 0, "escalations": 0,
                        "sentiment_total": 0.0, "ai_resolved": 0}

    for created_at, is_escalated, sentiment, message_count in rows:
        key = created_at.date().isoformat()
        bucket = buckets.get(key)
        if bucket is None:
            continue
        bucket["conversations"] += 1
        bucket["sentiment_total"] += float(sentiment or 0)
        if is_escalated:
            bucket["escalations"] += 1
        elif (message_count or 0) >= 2:
            bucket["ai_resolved"] += 1

    return [
        {
            "date": b["date"],
            "conversations": b["conversations"],
            "escalations": b["escalations"],
            "ai_resolved": b["ai_resolved"],
            "avg_sentiment": round(b["sentiment_total"] / b["conversations"], 3)
            if b["conversations"] else 0.0,
        }
        for b in buckets.values()
    ]


async def tool_usage(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                ToolCallLog.tool_name,
                func.count(ToolCallLog.id),
                func.avg(ToolCallLog.duration_ms),
            ).group_by(ToolCallLog.tool_name)
        )
    ).all()
    failures = dict(
        (
            await db.execute(
                select(ToolCallLog.tool_name, func.count(ToolCallLog.id))
                .where(ToolCallLog.success.is_(False))
                .group_by(ToolCallLog.tool_name)
            )
        ).all()
    )
    out = [
        {
            "tool": name,
            "calls": int(calls),
            "success_rate": round((int(calls) - int(failures.get(name, 0))) / int(calls) * 100, 1)
            if int(calls) else 100.0,
            "avg_duration_ms": round(float(avg or 0), 1),
        }
        for name, calls, avg in rows
    ]
    out.sort(key=lambda d: d["calls"], reverse=True)
    return out


async def sentiment_distribution(db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Conversation.last_sentiment, func.count(Conversation.id))
            .group_by(Conversation.last_sentiment)
        )
    ).all()
    total = sum(int(c) for _, c in rows) or 1
    order = ["very_negative", "negative", "neutral", "positive", "very_positive"]
    data = {s: int(c) for s, c in rows}
    return [
        {
            "sentiment": s,
            "count": data.get(s, 0),
            "percentage": round(data.get(s, 0) / total * 100, 1),
        }
        for s in order
    ]


async def top_articles(db: AsyncSession, limit: int = 5) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(KBDocument.title, KBDocument.slug, KBDocument.view_count,
                   KBDocument.helpful_count)
            .order_by(KBDocument.view_count.desc())
            .limit(limit)
        )
    ).all()
    return [
        {"title": t, "slug": s, "views": int(v), "helpful": int(h)} for t, s, v, h in rows
    ]


async def dashboard(db: AsyncSession, days: int = 30) -> dict[str, Any]:
    return {
        "kpis": await kpi_summary(db, days),
        "intents": await intent_breakdown(db),
        "channels": await channel_breakdown(db),
        "timeseries": await timeseries(db, min(days, 30)),
        "tools": await tool_usage(db),
        "sentiment": await sentiment_distribution(db),
        "top_articles": await top_articles(db),
        "generated_at": _now().isoformat(),
    }
