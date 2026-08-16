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
    if provider == "anthropic":
        try:
            from app.services.llm.anthropic_provider import AnthropicProvider

            log.info("LLM provider: Anthropic (%s)", settings.LLM_MODEL)
            return AnthropicProvider()
        except Exception as exc:
            log.warning("Falling back to the mock planner - %s", exc)
    log.info("LLM provider: mock rule-based planner (no API key configured)")
    return MockProvider()
