"""Conversation, message, ticket and chat schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    ChannelType,
    ConversationStatus,
    EscalationReason,
    Intent,
    MessageRole,
    Sentiment,
    TicketPriority,
    TicketStatus,
)
from app.schemas.common import ORMModel


# ---------------------------------------------------------------- messages --
class Citation(BaseModel):
    document_id: str
    title: str
    snippet: str
    score: float
    slug: str | None = None


class ToolTrace(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    duration_ms: int = 0
    error: str | None = None


class MessageOut(ORMModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime
    intent: Intent | None = None
    intent_confidence: float | None = None
    sentiment: Sentiment | None = None
    sentiment_score: float | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int | None = None
    audio_duration_ms: int | None = None
    transcript_confidence: float | None = None
    model: str | None = None


# ----------------------------------------------------------- conversations --
class ConversationOut(ORMModel):
    id: str
    customer_id: str | None = None
    channel: ChannelType
    status: ConversationStatus
    title: str
    language: str
    primary_intent: Intent
    last_sentiment: Sentiment
    sentiment_score: float
    is_escalated: bool
    escalation_reason: str | None = None
    assigned_agent_id: str | None = None
    resolved_by_ai: bool
    message_count: int
    total_tokens: int
    voice_seconds: float
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    channel: ChannelType = ChannelType.WEB_CHAT
    language: str = "en"
    anonymous_key: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------- chat ---
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None
    channel: ChannelType = ChannelType.WEB_CHAT
    language: str = "en"
    anonymous_key: str | None = None
    # Voice clients set this so replies stay short and speakable.
    voice_mode: bool = False


class AgentReply(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    intent: Intent
    intent_confidence: float
    sentiment: Sentiment
    sentiment_score: float
    citations: list[Citation] = Field(default_factory=list)
    tool_trace: list[ToolTrace] = Field(default_factory=list)
    escalated: bool = False
    escalation_reason: EscalationReason | None = None
    suggested_replies: list[str] = Field(default_factory=list)
    handoff_ticket_number: str | None = None
    latency_ms: int = 0
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


# ---------------------------------------------------------------- tickets ---
class TicketOut(ORMModel):
    id: str
    ticket_number: str
    conversation_id: str | None = None
    customer_id: str | None = None
    assigned_agent_id: str | None = None
    subject: str
    description: str
    category: str
    status: TicketStatus
    priority: TicketPriority
    order_id: str | None = None
    created_by_agent: bool
    sla_due_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateTicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=240)
    description: str = Field(default="", max_length=8000)
    category: str = Intent.UNKNOWN.value
    priority: TicketPriority = TicketPriority.MEDIUM
    conversation_id: str | None = None
    order_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateTicketRequest(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assigned_agent_id: str | None = None
    resolution_note: str | None = None
    tags: list[str] | None = None


# --------------------------------------------------------------- feedback ---
class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    resolved: bool = True
    comment: str | None = Field(default=None, max_length=2000)
    nps: int | None = Field(default=None, ge=0, le=10)


class FeedbackOut(ORMModel):
    id: str
    conversation_id: str
    rating: int
    resolved: bool
    comment: str | None = None
    nps: int | None = None
    created_at: datetime


# ------------------------------------------------------------- handoff -----
class HandoffRequest(BaseModel):
    reason: EscalationReason = EscalationReason.CUSTOMER_REQUEST
    note: str | None = None
