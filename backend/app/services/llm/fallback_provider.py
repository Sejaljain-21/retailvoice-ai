"""Fallback LLM provider that chains multiple backends.

If the primary provider fails (e.g., rate limit 429, timeout, or API error),
it automatically fails over to the next configured provider (e.g., Groq -> Gemini
or Gemini -> Groq), ensuring zero downtime and resilient voice conversations.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.services.llm.base import BaseLLMProvider, LLMResult, ToolSpec

log = get_logger(__name__)


class FallbackProvider(BaseLLMProvider):
    """Executes completions against a primary provider, failing over on error."""

    def __init__(self, providers: list[BaseLLMProvider], *, cooldown_seconds: float = 60.0) -> None:
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        self.providers = list(providers)
        self.cooldown_seconds = cooldown_seconds
        # Track provider cooldowns: provider_index -> cooldown_until_timestamp
        self._cooldowns: dict[int, float] = {}

    @property
    def primary(self) -> BaseLLMProvider:
        return self.providers[0]

    @property
    def name(self) -> str:
        chain_names = " -> ".join(p.name for p in self.providers)
        return f"{self.primary.name} (fallback: {chain_names})"

    @property
    def model(self) -> str:
        return getattr(self.primary, "model", "")

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        now = time.time()
        last_exc: Exception | None = None

        # Order providers: active providers first, then any currently in cooldown
        candidate_indices = [
            i for i in range(len(self.providers)) if self._cooldowns.get(i, 0) <= now
        ]
        # If all real providers are in cooldown, reset and try all
        if not candidate_indices:
            candidate_indices = list(range(len(self.providers)))

        for idx in candidate_indices:
            provider = self.providers[idx]
            try:
                result = await provider.complete(
                    system=system,
                    messages=messages,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                # Success - clear cooldown for this provider if any
                self._cooldowns.pop(idx, None)
                return result
            except Exception as exc:
                last_exc = exc
                self._cooldowns[idx] = now + self.cooldown_seconds
                next_name = (
                    self.providers[candidate_indices[candidate_indices.index(idx) + 1]].name
                    if candidate_indices.index(idx) + 1 < len(candidate_indices)
                    else "none"
                )
                log.warning(
                    "LLM provider '%s' failed (%s). Failing over to '%s' (cooldown %ds)...",
                    provider.name,
                    exc,
                    next_name,
                    int(self.cooldown_seconds),
                )

        log.error("All providers in fallback chain failed: %s", last_exc)
        if last_exc:
            raise last_exc
        raise RuntimeError("No LLM provider was able to complete the request.")

    async def healthcheck(self) -> dict[str, Any]:
        results = []
        for p in self.providers:
            try:
                results.append(await p.healthcheck())
            except Exception as exc:
                results.append({"provider": p.name, "status": "error", "detail": str(exc)})
        return {
            "provider": self.name,
            "status": "ok" if any(r.get("status") == "ok" for r in results) else "error",
            "chain": results,
        }
