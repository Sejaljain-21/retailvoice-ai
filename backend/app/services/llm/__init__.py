"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.services.llm.base import (
    BaseLLMProvider,
    LLMResult,
    ToolSpec,
    ToolUse,
    assistant_message,
    last_user_text,
    text_block,
    tool_result_message,
    user_message,
)
from app.services.llm.mock_provider import MockProvider

log = get_logger(__name__)

__all__ = [
    "BaseLLMProvider",
    "LLMResult",
    "ToolSpec",
    "ToolUse",
    "assistant_message",
    "get_llm",
    "last_user_text",
    "text_block",
    "tool_result_message",
    "user_message",
]


@lru_cache
def get_llm() -> BaseLLMProvider:
    provider = settings.resolved_llm_provider
    available: list[BaseLLMProvider] = []

    def try_add_gemini() -> None:
        if settings.GEMINI_API_KEY.strip():
            try:
                from app.services.llm.openai_compatible_provider import GeminiProvider

                available.append(GeminiProvider())
                log.info("Loaded LLM provider: Google Gemini (%s)", settings.GEMINI_MODEL)
            except Exception as exc:
                log.warning("Failed initializing GeminiProvider: %s", exc)

    def try_add_groq() -> None:
        if settings.GROQ_API_KEY.strip():
            try:
                from app.services.llm.openai_compatible_provider import GroqProvider

                available.append(GroqProvider())
                log.info("Loaded LLM provider: Groq (%s)", settings.GROQ_MODEL)
            except Exception as exc:
                log.warning("Failed initializing GroqProvider: %s", exc)

    def try_add_anthropic() -> None:
        if settings.ANTHROPIC_API_KEY.strip():
            try:
                from app.services.llm.anthropic_provider import AnthropicProvider

                available.append(AnthropicProvider())
                log.info("Loaded LLM provider: Anthropic (%s)", settings.LLM_MODEL)
            except Exception as exc:
                log.warning("Failed initializing AnthropicProvider: %s", exc)

    if provider == "gemini":
        try_add_gemini()
        try_add_groq()
        try_add_anthropic()
    elif provider == "groq":
        try_add_groq()
        try_add_gemini()
        try_add_anthropic()
    elif provider == "anthropic":
        try_add_anthropic()
        try_add_gemini()
        try_add_groq()
    else:
        # Default / auto: Gemini primary if configured, Groq as fallback
        try_add_gemini()
        try_add_groq()
        try_add_anthropic()

    if not available or provider == "mock":
        log.info("LLM provider: mock rule-based planner")
        return MockProvider()

    # Always append MockProvider as safety net at the end of the chain
    available.append(MockProvider())

    if len(available) == 1:
        return available[0]

    from app.services.llm.fallback_provider import FallbackProvider

    log.info(
        "LLM provider active with fallback chain: %s",
        " -> ".join(p.name for p in available),
    )
    return FallbackProvider(available)
