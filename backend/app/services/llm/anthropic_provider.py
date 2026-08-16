"""Claude-backed LLM provider (Anthropic Messages API with tool use)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.services.llm.base import BaseLLMProvider, LLMResult, ToolSpec, ToolUse

log = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                "The `anthropic` package is not installed. "
                "Run `pip install anthropic` or set LLM_PROVIDER=mock."
            ) from exc

        key = (api_key or settings.ANTHROPIC_API_KEY).strip()
        if not key:
            raise ProviderError("ANTHROPIC_API_KEY is empty; set it or use LLM_PROVIDER=mock.")

        self.model = model or settings.LLM_MODEL
        self._client = AsyncAnthropic(api_key=key, max_retries=2, timeout=60.0)

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = [t.to_anthropic() for t in tools]

        try:
            response = await self._client.messages.create(**kwargs)
        except Exception as exc:
            # One retry on the cheaper/faster model before giving up.
            log.warning("Claude call failed on %s (%s); trying fallback model.", self.model, exc)
            try:
                kwargs["model"] = settings.LLM_FALLBACK_MODEL
                response = await self._client.messages.create(**kwargs)
            except Exception as exc2:  # pragma: no cover - network dependent
                raise ProviderError(f"Anthropic request failed: {exc2}") from exc2

        text_parts: list[str] = []
        tool_uses: list[ToolUse] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(
                    ToolUse(id=block.id, name=block.name, input=dict(block.input or {}))
                )

        return LLMResult(
            text="".join(text_parts).strip(),
            tool_uses=tool_uses,
            stop_reason=response.stop_reason or "end_turn",
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            model=response.model,
            provider=self.name,
        )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            res = await self._client.messages.create(
                model=self.model,
                max_tokens=8,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"provider": self.name, "status": "ok", "model": res.model}
        except Exception as exc:  # pragma: no cover
            return {"provider": self.name, "status": "error", "detail": str(exc)}
