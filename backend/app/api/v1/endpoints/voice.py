"""REST half of the voice pipeline: transcribe, synthesize, and a one-shot turn.

The streaming half lives in `app/ws/voice_ws.py`. These endpoints exist so the
pipeline can be driven from curl, Postman or a mobile client that does not hold
a socket open.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, File, Form, UploadFile

from app.agent import get_or_create_conversation, run_turn
from app.api.deps import DbSession, OptionalUser
from app.api.v1.endpoints.chat import _to_reply
from app.core.config import settings
from app.core.exceptions import ValidationError_
from app.models.enums import ChannelType
from app.schemas.voice import (
    SynthesisRequest,
    SynthesisResponse,
    TranscriptionResponse,
    VoiceTurnResponse,
)
from app.services.speech import get_stt, get_tts, to_speakable

router = APIRouter()

MAX_AUDIO_BYTES = 12 * 1024 * 1024   # 12 MB ≈ 10 minutes of Opus


@router.get("/config")
async def voice_config() -> dict:
    """What the client needs to know before starting a voice session."""
    stt, tts = get_stt(), get_tts()
    return {
        "stt_provider": stt.name,
        "stt_client_side": stt.client_side,
        "tts_provider": tts.name,
        "tts_client_side": tts.client_side,
        "max_session_seconds": settings.VOICE_MAX_SESSION_SECONDS,
        "silence_timeout_ms": settings.VOICE_SILENCE_TIMEOUT_MS,
        "websocket_path": "/ws/voice",
        "supported_languages": ["en", "hi", "ta", "te", "es", "fr"],
    }


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(..., description="webm/ogg/wav/mp3 audio"),
    language: str = Form("en"),
) -> TranscriptionResponse:
    data = await audio.read()
    if not data:
        raise ValidationError_("The uploaded audio file is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise ValidationError_("Audio exceeds the 12 MB limit.")

    result = await get_stt().transcribe(
        data, language=language, mime_type=audio.content_type or "audio/webm"
    )
    return TranscriptionResponse(**{k: v for k, v in result.items() if k != "note"})


@router.post("/synthesize", response_model=SynthesisResponse)
async def synthesize(payload: SynthesisRequest) -> SynthesisResponse:
    result = await get_tts().synthesize(
        to_speakable(payload.text),
        voice_id=payload.voice_id,
        language=payload.language,
        speed=payload.speed,
    )
    return SynthesisResponse(**result)


@router.post("/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    db: DbSession,
    user: OptionalUser,
    audio: UploadFile | None = File(None),
    text: str | None = Form(None),
    conversation_id: str | None = Form(None),
    language: str = Form("en"),
    speak: bool = Form(True),
) -> VoiceTurnResponse:
    """One complete voice turn: audio (or client transcript) -> agent -> audio.

    Send `audio` when the server does recognition, or `text` when the browser
    already transcribed the utterance with the Web Speech API.
    """
    if not audio and not text:
        raise ValidationError_("Provide either an `audio` file or a `text` transcript.")

    if audio is not None:
        data = await audio.read()
        if len(data) > MAX_AUDIO_BYTES:
            raise ValidationError_("Audio exceeds the 12 MB limit.")
        stt_result = await get_stt().transcribe(
            data, language=language, mime_type=audio.content_type or "audio/webm"
        )
        transcript = TranscriptionResponse(
            **{k: v for k, v in stt_result.items() if k != "note"}
        )
    else:
        transcript = TranscriptionResponse(
            text=text or "", confidence=1.0, language=language, provider="client"
        )

    if not transcript.text.strip():
        raise ValidationError_(
            "No speech was recognised. If STT_PROVIDER=browser, send the transcript "
            "in the `text` field instead of an audio file."
        )

    conversation = await get_or_create_conversation(
        db, conversation_id=conversation_id, user=user,
        channel=ChannelType.VOICE, language=transcript.language,
    )
    turn = await run_turn(
        db,
        conversation=conversation,
        user=user,
        text=transcript.text,
        voice_mode=True,
        audio_duration_ms=transcript.duration_ms or None,
        transcript_confidence=transcript.confidence or None,
    )

    audio_out = None
    if speak:
        synth = await get_tts().synthesize(turn.speakable, language=transcript.language)
        audio_out = SynthesisResponse(**synth)

    return VoiceTurnResponse(
        transcript=transcript, reply=_to_reply(turn), audio=audio_out
    )


@router.post("/tts-preview")
async def tts_preview(payload: SynthesisRequest) -> dict:
    """Small helper the frontend uses to check audio playback end-to-end."""
    result = await get_tts().synthesize(to_speakable(payload.text), speed=payload.speed)
    size = len(base64.b64decode(result["audio_base64"])) if result["audio_base64"] else 0
    return {**result, "bytes": size}
