"""Speech-to-text and text-to-speech providers.

Four STT backends and four TTS backends share one interface each, selected by
`STT_PROVIDER` / `TTS_PROVIDER`. The default on both sides is **browser**: the
client performs recognition/synthesis with the Web Speech API, which keeps the
project runnable with no keys, no model downloads and no audio round-trip.
"""

from __future__ import annotations

import abc
import asyncio
import base64
import io
import math
import struct
import wave
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger

log = get_logger(__name__)


# ===========================================================================
# Speech to text
# ===========================================================================
class BaseSTT(abc.ABC):
    name = "base"
    # True when the client is expected to do recognition itself.
    client_side = False

    @abc.abstractmethod
    async def transcribe(
        self, audio: bytes, *, language: str = "en", mime_type: str = "audio/webm"
    ) -> dict[str, Any]:
        """Return {"text", "confidence", "language", "duration_ms", "provider"}."""


class BrowserSTT(BaseSTT):
    """No server-side recognition - the browser sends text instead of audio."""

    name = "browser"
    client_side = True

    async def transcribe(self, audio: bytes, *, language: str = "en",
                         mime_type: str = "audio/webm") -> dict[str, Any]:
        return {
            "text": "",
            "confidence": 0.0,
            "language": language,
            "duration_ms": 0,
            "provider": self.name,
            "note": "Client-side recognition: send the transcript as a `text` event.",
        }


class MockSTT(BaseSTT):
    """Deterministic stub so the pipeline can be exercised in tests."""

    name = "mock"
    SAMPLES = [
        "Where is my order?",
        "I want to return the shoes I bought last week.",
        "Do you have the wireless headphones in stock?",
        "My delivery is three days late and nobody has called me.",
        "Can I speak to a human agent please?",
    ]

    async def transcribe(self, audio: bytes, *, language: str = "en",
                         mime_type: str = "audio/webm") -> dict[str, Any]:
        idx = (len(audio) // 997) % len(self.SAMPLES)
        return {
            "text": self.SAMPLES[idx],
            "confidence": 0.93,
            "language": language,
            "duration_ms": max(400, len(audio) // 32),
            "provider": self.name,
        }


class WhisperSTT(BaseSTT):
    """Local faster-whisper. `pip install -r requirements-optional.txt`."""

    name = "whisper"

    def __init__(self) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                "faster-whisper is not installed. Install requirements-optional.txt "
                "or set STT_PROVIDER=browser."
            ) from exc
        log.info("Loading Whisper model %s on %s", settings.WHISPER_MODEL_SIZE,
                 settings.WHISPER_DEVICE)
        self._model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type="int8",
        )

    async def transcribe(self, audio: bytes, *, language: str = "en",
                         mime_type: str = "audio/webm") -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            segments, info = self._model.transcribe(
                io.BytesIO(audio),
                language=None if language in ("auto", "") else language,
                vad_filter=True,
                beam_size=5,
            )
            parts, probs = [], []
            for seg in segments:
                parts.append(seg.text)
                probs.append(math.exp(seg.avg_logprob))
            return {
                "text": " ".join(parts).strip(),
                "confidence": round(sum(probs) / len(probs), 3) if probs else 0.0,
                "language": info.language or language,
                "duration_ms": int((info.duration or 0) * 1000),
                "provider": self.name,
            }

        return await asyncio.to_thread(_run)


class DeepgramSTT(BaseSTT):
    """Hosted streaming-quality STT over the pre-recorded REST endpoint."""

    name = "deepgram"
    ENDPOINT = "https://api.deepgram.com/v1/listen"

    def __init__(self) -> None:
        if not settings.DEEPGRAM_API_KEY.strip():
            raise ProviderError("DEEPGRAM_API_KEY is not set.")

    async def transcribe(self, audio: bytes, *, language: str = "en",
                         mime_type: str = "audio/webm") -> dict[str, Any]:
        import httpx

        params = {
            "model": "nova-2",
            "smart_format": "true",
            "punctuate": "true",
            "language": language or "en",
        }
        headers = {
            "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
            "Content-Type": mime_type,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(self.ENDPOINT, params=params, headers=headers, content=audio)
        if resp.status_code >= 400:
            raise ProviderError(f"Deepgram error {resp.status_code}: {resp.text[:200]}")

        payload = resp.json()
        alt = payload["results"]["channels"][0]["alternatives"][0]
        return {
            "text": alt.get("transcript", ""),
            "confidence": round(float(alt.get("confidence", 0.0)), 3),
            "language": language,
            "duration_ms": int(payload.get("metadata", {}).get("duration", 0) * 1000),
            "provider": self.name,
        }


@lru_cache
def get_stt() -> BaseSTT:
    provider = settings.STT_PROVIDER
    try:
        match provider:
            case "whisper":
                return WhisperSTT()
            case "deepgram":
                return DeepgramSTT()
            case "mock":
                return MockSTT()
            case _:
                return BrowserSTT()
    except Exception as exc:
        log.warning("STT provider %s unavailable (%s) - using browser mode.", provider, exc)
        return BrowserSTT()


# ===========================================================================
# Text to speech
# ===========================================================================
class BaseTTS(abc.ABC):
    name = "base"
    client_side = False
    mime_type = "audio/wav"

    @abc.abstractmethod
    async def synthesize(
        self, text: str, *, voice_id: str | None = None,
        language: str = "en", speed: float = 1.0,
    ) -> dict[str, Any]:
        """Return {"audio_base64", "mime_type", "duration_ms", "provider", "use_client_tts"}."""


def _silent_wav(duration_ms: int, sample_rate: int = 22050) -> bytes:
    """A valid WAV of silence - lets clients exercise playback without a voice."""
    frames = int(sample_rate * duration_ms / 1000)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(struct.pack(f"<{frames}h", *([0] * frames)))
    return buf.getvalue()


def _estimate_duration_ms(text: str, speed: float = 1.0) -> int:
    """~165 spoken words per minute."""
    words = max(1, len(text.split()))
    return int(words / 165 * 60_000 / max(0.5, speed))


class BrowserTTS(BaseTTS):
    """Tells the client to speak the text with `window.speechSynthesis`."""

    name = "browser"
    client_side = True

    async def synthesize(self, text: str, *, voice_id: str | None = None,
                         language: str = "en", speed: float = 1.0) -> dict[str, Any]:
        return {
            "audio_base64": "",
            "mime_type": "",
            "duration_ms": _estimate_duration_ms(text, speed),
            "provider": self.name,
            "use_client_tts": True,
            "text": text,
        }


class MockTTS(BaseTTS):
    name = "mock"

    async def synthesize(self, text: str, *, voice_id: str | None = None,
                         language: str = "en", speed: float = 1.0) -> dict[str, Any]:
        duration = _estimate_duration_ms(text, speed)
        audio = _silent_wav(min(duration, 4000), settings.TTS_SAMPLE_RATE)
        return {
            "audio_base64": base64.b64encode(audio).decode(),
            "mime_type": "audio/wav",
            "duration_ms": duration,
            "provider": self.name,
            "use_client_tts": False,
            "text": text,
        }


class Pyttsx3TTS(BaseTTS):
    """Offline OS voices (SAPI5 on Windows, NSSpeechSynthesizer on macOS, espeak on Linux)."""

    name = "pyttsx3"

    def __init__(self) -> None:
        try:
            import pyttsx3  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("pyttsx3 is not installed.") from exc

    async def synthesize(self, text: str, *, voice_id: str | None = None,
                         language: str = "en", speed: float = 1.0) -> dict[str, Any]:
        import tempfile
        from pathlib import Path

        def _run() -> bytes:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", int(175 * speed))
            if voice_id:
                engine.setProperty("voice", voice_id)
            tmp = Path(tempfile.gettempdir()) / f"rv_tts_{abs(hash(text)) % 10**10}.wav"
            engine.save_to_file(text, str(tmp))
            engine.runAndWait()
            data = tmp.read_bytes() if tmp.exists() else b""
            tmp.unlink(missing_ok=True)
            return data

        audio = await asyncio.to_thread(_run)
        if not audio:
            raise ProviderError("pyttsx3 produced no audio.")
        return {
            "audio_base64": base64.b64encode(audio).decode(),
            "mime_type": "audio/wav",
            "duration_ms": _estimate_duration_ms(text, speed),
            "provider": self.name,
            "use_client_tts": False,
            "text": text,
        }


class ElevenLabsTTS(BaseTTS):
    """Hosted neural TTS - the highest quality option."""

    name = "elevenlabs"
    mime_type = "audio/mpeg"

    def __init__(self) -> None:
        if not settings.ELEVENLABS_API_KEY.strip():
            raise ProviderError("ELEVENLABS_API_KEY is not set.")

    async def synthesize(self, text: str, *, voice_id: str | None = None,
                         language: str = "en", speed: float = 1.0) -> dict[str, Any]:
        import httpx

        voice = voice_id or settings.ELEVENLABS_VOICE_ID
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={
                    "xi-api-key": settings.ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {
                        "stability": 0.45,
                        "similarity_boost": 0.75,
                        "speed": speed,
                    },
                },
            )
        if resp.status_code >= 400:
            raise ProviderError(f"ElevenLabs error {resp.status_code}: {resp.text[:200]}")
        return {
            "audio_base64": base64.b64encode(resp.content).decode(),
            "mime_type": "audio/mpeg",
            "duration_ms": _estimate_duration_ms(text, speed),
            "provider": self.name,
            "use_client_tts": False,
            "text": text,
        }


@lru_cache
def get_tts() -> BaseTTS:
    provider = settings.TTS_PROVIDER
    try:
        match provider:
            case "elevenlabs":
                return ElevenLabsTTS()
            case "pyttsx3":
                return Pyttsx3TTS()
            case "mock":
                return MockTTS()
            case _:
                return BrowserTTS()
    except Exception as exc:
        log.warning("TTS provider %s unavailable (%s) - using browser mode.", provider, exc)
        return BrowserTTS()


# ===========================================================================
# Speakable-text helper
# ===========================================================================
def to_speakable(text: str) -> str:
    """Strip markdown so TTS doesn't read asterisks and hyphens aloud."""
    import re

    out = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    out = re.sub(r"\*(.+?)\*", r"\1", out)
    out = re.sub(r"`(.+?)`", r"\1", out)
    out = re.sub(r"^\s*[-*]\s+", "", out, flags=re.M)
    out = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", out)
    out = out.replace("₹", "rupees ")
    return re.sub(r"\n{2,}", ". ", out).replace("\n", ". ").strip()
