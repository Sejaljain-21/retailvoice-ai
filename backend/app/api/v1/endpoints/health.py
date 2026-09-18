"""Liveness, readiness and capability discovery."""

from __future__ import annotations

import platform
import time

from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.agent.tools import tool_names
from app.api.deps import DbSession
from app.core.config import settings
from app.services.embeddings import get_embedder
from app.services.llm import get_llm
from app.services.speech import get_stt, get_tts

router = APIRouter()
_STARTED_AT = time.time()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__, "uptime_s": round(time.time() - _STARTED_AT)}


@router.get("/ready")
async def ready(db: DbSession) -> dict:
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["database"] = f"error: {exc}"

    checks["llm"] = get_llm().name
    checks["stt"] = get_stt().name
    checks["tts"] = get_tts().name
    checks["embeddings"] = get_embedder().name

    healthy = all(not v.startswith("error") for v in checks.values())
    return {"status": "ready" if healthy else "degraded", "checks": checks}


@router.get("/capabilities")
async def capabilities() -> dict:
    """What this deployment can do - the frontend adapts its UI to this."""
    stt, tts = get_stt(), get_tts()
    return {
        "app": settings.APP_NAME,
        "version": __version__,
        "environment": settings.APP_ENV,
        "python": platform.python_version(),
        "llm": {
            "provider": get_llm().name,
            "model": (
                getattr(get_llm(), "model", None)
                or (settings.GEMINI_MODEL if "gemini" in get_llm().name.lower()
                    else settings.GROQ_MODEL if "groq" in get_llm().name.lower()
                    else settings.LLM_MODEL if "anthropic" in get_llm().name.lower()
                    else "mock-planner-v1")
            ),
            "max_tool_iterations": settings.AGENT_MAX_TOOL_ITERATIONS,
        },
        "speech": {
            "stt_provider": stt.name,
            "stt_client_side": stt.client_side,
            "tts_provider": tts.name,
            "tts_client_side": tts.client_side,
        },
        "retrieval": {
            "embedding_provider": get_embedder().name,
            "dim": get_embedder().dim,
            "top_k": settings.RAG_TOP_K,
        },
        "tools": tool_names(),
        "channels": ["web_chat", "voice", "email", "whatsapp", "phone"],
        "features": {
            "pii_redaction": settings.ENABLE_PII_REDACTION,
            "anonymous_order_lookup": settings.ALLOW_ANONYMOUS_ORDER_LOOKUP,
            "voice_websocket": "/ws/voice",
        },
    }
