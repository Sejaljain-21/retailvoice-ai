"""Analytics / dashboard schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class KpiSummary(BaseModel):
    total_conversations: int
    conversations_today: int
    active_conversations: int
    ai_resolved: int
    escalated: int
    containment_rate: float = Field(description="% of conversations closed without a human")
    deflection_rate: float = Field(description="% of conversations that never opened a ticket")
    avg_csat: float
    csat_responses: int
    avg_handle_time_s: float
    avg_first_response_ms: float
    open_tickets: int
    total_voice_minutes: float
    total_tokens: int
    estimated_cost_usd: float


class IntentBreakdown(BaseModel):
    intent: str
    count: int
    percentage: float
    avg_sentiment: float
    escalation_rate: float


class ChannelBreakdown(BaseModel):
    channel: str
    count: int
    percentage: float
    containment_rate: float


class TimeSeriesPoint(BaseModel):
    date: str
    conversations: int
    escalations: int
    avg_sentiment: float
    ai_resolved: int


class ToolUsage(BaseModel):
    tool: str
    calls: int
    success_rate: float
    avg_duration_ms: float


class SentimentDistribution(BaseModel):
    sentiment: str
    count: int
    percentage: float


class AnalyticsDashboard(BaseModel):
    kpis: KpiSummary
    intents: list[IntentBreakdown]
    channels: list[ChannelBreakdown]
    timeseries: list[TimeSeriesPoint]
    tools: list[ToolUsage]
    sentiment: list[SentimentDistribution]
    top_articles: list[dict]
    generated_at: str
