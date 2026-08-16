"""Voice pipeline schemas (REST + WebSocket envelopes)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.support import AgentReply


class TranscriptionResponse(BaseModel):
    text: str
    confidence: float
    language: str = "en"
    duration_ms: int = 0
    provider: str = "mock"


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    voice_id: str | None = None
    language: str = "en"
    speed: float = Field(1.0, ge=0.5, le=2.0)


class SynthesisResponse(BaseModel):
    audio_base64: str
    mime_type: str = "audio/wav"
    duration_ms: int = 0
    provider: str = "mock"
    # When the provider is "browser" the client is told to use SpeechSynthesis.
    use_client_tts: bool = False
    text: str = ""


class VoiceTurnResponse(BaseModel):
    transcript: TranscriptionResponse
    reply: AgentReply
    audio: SynthesisResponse | None = None


# --------------------------------------------------------------- WebSocket --
WSClientEventType = Literal[
    "start", "audio_chunk", "audio_end", "text", "barge_in", "stop", "ping"
]
WSServerEventType = Literal[
    "ready", "partial_transcript", "final_transcript", "thinking",
    "tool_call", "reply_delta", "reply", "audio", "escalated", "error", "pong", "closed",
]


class WSClientEvent(BaseModel):
    type: WSClientEventType
    # base64 audio for audio_chunk, plain text for `text`
    data: str | None = None
    language: str = "en"
    conversation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WSServerEvent(BaseModel):
    type: WSServerEventType
    data: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = None
    seq: int = 0
