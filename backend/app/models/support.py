"""Conversations, messages, tool traces, tickets, escalations and CSAT."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import (
    ChannelType,
    ConversationStatus,
    Intent,
    MessageRole,
    Sentiment,
    TicketPriority,
    TicketStatus,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    customer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    # Lets anonymous storefront visitors keep a thread before signing in.
    anonymous_key: Mapped[str | None] = mapped_column(String(64), index=True)

    channel: Mapped[str] = mapped_column(String(24), default=ChannelType.WEB_CHAT, index=True)
    status: Mapped[str] = mapped_column(String(24), default=ConversationStatus.ACTIVE, index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    language: Mapped[str] = mapped_column(String(12), default="en")

    primary_intent: Mapped[str] = mapped_column(String(40), default=Intent.UNKNOWN, index=True)
    last_sentiment: Mapped[str] = mapped_column(String(20), default=Sentiment.NEUTRAL)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)

    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalation_reason: Mapped[str | None] = mapped_column(String(40))
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)

    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    voice_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    conversation_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    customer: Mapped["User | None"] = relationship(
        back_populates="conversations", foreign_keys=[customer_id]
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
        lazy="selectin",
    )
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="conversation", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Conversation {self.id} {self.channel} {self.status}>"


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default=MessageRole.USER, index=True)
    content: Mapped[str] = mapped_column(Text, default="")

    # Voice metadata
    audio_url: Mapped[str | None] = mapped_column(String(512))
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer)
    transcript_confidence: Mapped[float | None] = mapped_column(Float)

    # NLU annotations
    intent: Mapped[str | None] = mapped_column(String(40))
    intent_confidence: Mapped[float | None] = mapped_column(Float)
    sentiment: Mapped[str | None] = mapped_column(String(20))
    sentiment_score: Mapped[float | None] = mapped_column(Float)

    # Agent telemetry
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(60))
    was_redacted: Mapped[bool] = mapped_column(Boolean, default=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class ToolCallLog(UUIDMixin, TimestampMixin, Base):
    """One row per tool invocation - the audit trail for what the agent did."""

    __tablename__ = "tool_call_logs"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    tool_name: Mapped[str] = mapped_column(String(64), index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)


class Ticket(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    ticket_number: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)

    subject: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default=Intent.UNKNOWN, index=True)
    status: Mapped[str] = mapped_column(String(24), default=TicketStatus.OPEN, index=True)
    priority: Mapped[str] = mapped_column(String(16), default=TicketPriority.MEDIUM, index=True)

    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    created_by_agent: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    customer: Mapped["User | None"] = relationship(
        back_populates="tickets", foreign_keys=[customer_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ticket {self.ticket_number} {self.status}>"


class Feedback(UUIDMixin, TimestampMixin, Base):
    """Post-conversation CSAT survey."""

    __tablename__ = "feedback"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, index=True
    )
    rating: Mapped[int] = mapped_column(Integer)          # 1..5 CSAT
    resolved: Mapped[bool] = mapped_column(Boolean, default=True)
    comment: Mapped[str | None] = mapped_column(Text)
    nps: Mapped[int | None] = mapped_column(Integer)      # 0..10

    conversation: Mapped["Conversation"] = relationship(back_populates="feedback")
