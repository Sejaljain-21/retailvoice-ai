"""Realtime voice WebSocket.

Protocol (JSON text frames both ways - see `app/schemas/voice.py`):

    client -> server            server -> client
    ------------------------    ---------------------------------------------
    start                       ready            {conversation_id, providers}
    audio_chunk (base64)        partial_transcript
    audio_end                   final_transcript {text, confidence}
    text        (browser STT,   thinking         {intent, sentiment}
      +confidence)               tool_call        {tool, arguments}
    barge_in                    tool_result      {tool, success, duration_ms}
    stop                        reply_delta      {text}      (streamed typing)
    ping                        reply            {text, suggested_replies, ...}
                                audio            {audio_base64 | use_client_tts}
                                escalated        {reason, ticket_number}
                                clarify          {text, message} (low-confidence
                                                   transcript - confirm before acting)
                                error / pong / closed

Two modes are supported on the same socket:
  * server-side STT - client streams `audio_chunk` frames, server transcribes;
  * browser STT     - client sends a `text` frame with the finished transcript.

A transcript below `LOW_CONFIDENCE_THRESHOLD` isn't acted on immediately: the
server asks the customer to confirm it via a `clarify` frame and holds it in
`VoiceSession.pending_transcript` until the next frame says yes, no, or simply
restates the request.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.agent import get_or_create_conversation, run_turn
from app.agent.orchestrator import close_conversation
from app.api.deps import user_from_query_token
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.models.enums import ChannelType
from app.models.support import Conversation
from app.services.speech import get_stt, get_tts, to_speakable

log = get_logger(__name__)
router = APIRouter()

MAX_BUFFERED_AUDIO = 12 * 1024 * 1024
REPLY_CHUNK_WORDS = 6

# Below this, a transcript is confirmed with the customer before it is acted on.
# Exact 0.0 usually means the recogniser didn't measure confidence at all (a common
# browser quirk), so it's treated as "no signal" rather than "definitely wrong".
LOW_CONFIDENCE_THRESHOLD = 0.6
_AFFIRMATIVE = {"yes", "yeah", "yep", "yup", "correct", "right", "haan", "ha", "sahi"}
_NEGATIVE = {"no", "nope", "nah", "wrong", "incorrect", "nahi", "galat"}


class VoiceSession:
    """One live call. Owns the audio buffer, sequence numbers and cancellation."""

    def __init__(self, websocket: WebSocket, conversation_id: str | None, language: str) -> None:
        self.ws = websocket
        self.conversation_id = conversation_id
        self.language = language
        self.audio = bytearray()
        self.seq = 0
        self.started_at = time.monotonic()
        self.busy = False
        self.cancelled = False
        self.turns = 0
        self.pending_transcript: str | None = None

    async def send(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.seq += 1
        await self.ws.send_text(
            json.dumps(
                {
                    "type": event,
                    "data": data or {},
                    "conversation_id": self.conversation_id,
                    "seq": self.seq,
                },
                default=str,
            )
        )

    @property
    def expired(self) -> bool:
        return time.monotonic() - self.started_at > settings.VOICE_MAX_SESSION_SECONDS


@router.websocket("/ws/voice")
async def voice_socket(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT access token (browsers cannot set headers)"),
    conversation_id: str | None = Query(None),
    language: str = Query("en"),
) -> None:
    await websocket.accept()
    session = VoiceSession(websocket, conversation_id, language)
    stt, tts = get_stt(), get_tts()

    try:
        # ---- Handshake ----------------------------------------------------
        async with session_scope() as db:
            user = await user_from_query_token(db, token)
            conversation = await get_or_create_conversation(
                db,
                conversation_id=conversation_id,
                user=user,
                channel=ChannelType.VOICE,
                language=language,
            )
            session.conversation_id = conversation.id
            user_id = user.id if user else None
            display_name = user.full_name.split()[0] if user else None

        await session.send(
            "ready",
            {
                "conversation_id": session.conversation_id,
                "stt_provider": stt.name,
                "stt_client_side": stt.client_side,
                "tts_provider": tts.name,
                "tts_client_side": tts.client_side,
                "greeting": (
                    f"Hi {display_name}, you're through to Aura at NovaMart. How can I help?"
                    if display_name
                    else "Hi, you're through to Aura at NovaMart. How can I help you today?"
                ),
                "silence_timeout_ms": settings.VOICE_SILENCE_TIMEOUT_MS,
                "max_session_seconds": settings.VOICE_MAX_SESSION_SECONDS,
            },
        )

        # ---- Event loop ---------------------------------------------------
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await session.send("error", {"message": "Frames must be valid JSON."})
                continue

            kind = event.get("type")

            if kind == "ping":
                await session.send("pong", {"uptime_s": round(time.monotonic() - session.started_at)})
                continue

            if session.expired:
                await session.send("error", {"message": "Voice session time limit reached.",
                                             "code": "session_expired"})
                break

            if kind == "start":
                session.audio.clear()
                session.cancelled = False
                await session.send("ready", {"listening": True})

            elif kind == "audio_chunk":
                chunk = event.get("data") or ""
                try:
                    session.audio.extend(base64.b64decode(chunk))
                except (ValueError, TypeError):
                    await session.send("error", {"message": "audio_chunk must be base64."})
                    continue
                if len(session.audio) > MAX_BUFFERED_AUDIO:
                    await session.send("error", {"message": "Audio buffer overflow; stopping."})
                    session.audio.clear()

            elif kind == "barge_in":
                # The customer started talking over the agent.
                session.cancelled = True
                await session.send("reply_delta", {"text": "", "interrupted": True})

            elif kind == "audio_end":
                if session.busy:
                    await session.send("error", {"message": "Still processing the previous turn."})
                    continue
                audio_bytes = bytes(session.audio)
                session.audio.clear()

                if stt.client_side:
                    await session.send(
                        "error",
                        {
                            "message": "Server STT is disabled (STT_PROVIDER=browser). "
                                       "Send a `text` frame with the transcript instead.",
                            "code": "client_side_stt",
                        },
                    )
                    continue
                if not audio_bytes:
                    await session.send("error", {"message": "No audio was received."})
                    continue

                result = await stt.transcribe(audio_bytes, language=session.language)
                transcript = (result.get("text") or "").strip()
                await session.send(
                    "final_transcript",
                    {"text": transcript, "confidence": result.get("confidence", 0.0),
                     "duration_ms": result.get("duration_ms", 0)},
                )
                if not transcript:
                    await session.send("error", {"message": "I didn't catch that - could you "
                                                            "say it again?"})
                    continue
                confidence = result.get("confidence", 0.0)
                resolved = await _resolve_transcript(session, transcript, confidence)
                if resolved is None:
                    continue
                await _handle_turn(
                    session, resolved, token=token,
                    audio_duration_ms=result.get("duration_ms"),
                    confidence=confidence,
                )

            elif kind == "text":
                if session.busy:
                    await session.send("error", {"message": "Still processing the previous turn."})
                    continue
                transcript = (event.get("data") or "").strip()
                if not transcript:
                    await session.send("error", {"message": "Empty transcript."})
                    continue
                raw_confidence = event.get("confidence")
                confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 1.0
                await session.send(
                    "final_transcript",
                    {"text": transcript, "confidence": confidence, "source": "client"},
                )
                resolved = await _resolve_transcript(session, transcript, confidence)
                if resolved is None:
                    continue
                await _handle_turn(session, resolved, token=token)

            elif kind == "stop":
                async with session_scope() as db:
                    conversation = (
                        await db.execute(
                            select(Conversation).where(Conversation.id == session.conversation_id)
                        )
                    ).scalars().first()
                    if conversation:
                        await close_conversation(db, conversation)
                await session.send("closed", {"turns": session.turns})
                break

            else:
                await session.send("error", {"message": f"Unknown event type '{kind}'."})

    except WebSocketDisconnect:
        log.info("Voice socket disconnected (conversation=%s)", session.conversation_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Voice socket failure")
        try:
            await session.send("error", {"message": "Internal error; closing the call.",
                                         "detail": str(exc)[:200]})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


async def _resolve_transcript(
    session: VoiceSession, transcript: str, confidence: float
) -> str | None:
    """Confirm low-confidence transcripts before acting on them.

    Returns the transcript to run through the agent, or None if a clarification
    was sent instead and the caller should wait for the next frame.
    """
    if session.pending_transcript is not None:
        pending = session.pending_transcript
        session.pending_transcript = None
        word = transcript.strip().lower()
        if word in _AFFIRMATIVE:
            return pending
        if word in _NEGATIVE:
            await session.send(
                "clarify", {"message": "No problem - go ahead and say that again."}
            )
            return None
        # They didn't say yes/no - most likely they just repeated or rephrased it,
        # so treat what they just said as the real query.
        return transcript

    if confidence and confidence < LOW_CONFIDENCE_THRESHOLD:
        session.pending_transcript = transcript
        await session.send(
            "clarify",
            {"text": transcript, "message": f'Just to confirm - did you say "{transcript}"?'},
        )
        return None

    return transcript


async def _handle_turn(
    session: VoiceSession,
    transcript: str,
    *,
    token: str | None,
    audio_duration_ms: int | None = None,
    confidence: float | None = None,
) -> None:
    """Run one agent turn and stream every stage back to the caller."""
    session.busy = True
    session.turns += 1
    try:
        async def on_event(event: str, payload: dict[str, Any]) -> None:
            if event in ("thinking", "tool_call", "tool_result", "escalated"):
                await session.send(event, payload)

        async with session_scope() as db:
            user = await user_from_query_token(db, token)
            conversation = await get_or_create_conversation(
                db, conversation_id=session.conversation_id, user=user,
                channel=ChannelType.VOICE, language=session.language,
            )
            turn = await run_turn(
                db,
                conversation=conversation,
                user=user,
                text=transcript,
                voice_mode=True,
                audio_duration_ms=audio_duration_ms,
                transcript_confidence=confidence,
                on_event=on_event,
            )

        # Stream the reply word-group by word-group so the UI can type it out.
        words = turn.reply.split()
        for i in range(0, len(words), REPLY_CHUNK_WORDS):
            if session.cancelled:
                break
            await session.send("reply_delta", {"text": " ".join(words[i:i + REPLY_CHUNK_WORDS]) + " "})
            await asyncio.sleep(0.045)

        await session.send(
            "reply",
            {
                "text": turn.reply,
                "speakable": turn.speakable,
                "intent": turn.intent.value,
                "sentiment": turn.sentiment.value,
                "sentiment_score": turn.sentiment_score,
                "escalated": turn.escalated,
                "handoff_ticket_number": turn.handoff_ticket_number,
                "suggested_replies": turn.suggested_replies,
                "citations": turn.citations,
                "tool_trace": [
                    {"tool": t["tool"], "success": t["success"], "duration_ms": t["duration_ms"]}
                    for t in turn.tool_trace
                ],
                "latency_ms": turn.latency_ms,
                "model": turn.model,
            },
        )

        if not session.cancelled:
            tts = get_tts()
            audio = await tts.synthesize(turn.speakable, language=session.language)
            await session.send("audio", audio)

    except Exception as exc:  # noqa: BLE001
        log.exception("Voice turn failed")
        await session.send("error", {"message": "That turn failed.", "detail": str(exc)[:200]})
    finally:
        session.busy = False
