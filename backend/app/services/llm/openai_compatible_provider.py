"""OpenAI-compatible LLM provider.

Powers both Google Gemini (free tier via Gemini's OpenAI-compatible endpoint)
and Groq (free tier ultra-fast Llama-3 inference via Groq's OpenAI API).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.services.llm.base import BaseLLMProvider, LLMResult, ToolSpec, ToolUse

log = get_logger(__name__)


def _to_openai_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal Anthropic-shaped message structure to OpenAI chat format."""
    out: list[dict[str, Any]] = []

    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            out.append({"role": role, "content": str(content or "")})
            continue

        # Check for tool_result blocks
        tool_results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
        if tool_results:
            for tr in tool_results:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.get("tool_use_id", ""),
                        "content": tr.get("content", ""),
                    }
                )
            continue

        # Check for assistant tool_use blocks
        tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
        text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        text_content = "\n".join(t for t in text_parts if t).strip()

        if tool_uses:
            tool_calls: list[dict[str, Any]] = []
            for tu in tool_uses:
                call_data: dict[str, Any] = {
                    "id": tu.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tu.get("name", ""),
                        "arguments": json.dumps(tu.get("input", {})),
                    },
                }
                if tu.get("extra_content"):
                    call_data["extra_content"] = tu["extra_content"]
                tool_calls.append(call_data)
            out.append(
                {
                    "role": "assistant",
                    "content": text_content or None,
                    "tool_calls": tool_calls,
                }
            )
        else:
            out.append({"role": role, "content": text_content})

    return out


def _to_openai_tools(tools: list[ToolSpec] | None) -> list[dict[str, Any]]:
    """Convert ToolSpec to OpenAI function calling specifications."""
    if not tools:
        return []
    result = []
    for t in tools:
        result.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
        )
    return result


class OpenAICompatibleProvider(BaseLLMProvider):
    """Generic async provider for endpoints speaking the OpenAI chat completions format."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 45.0,
    ) -> None:
        key = api_key.strip()
        if not key:
            raise ProviderError(f"API key for {name} is empty. Please set it in .env.")
        self.name = name
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._endpoint = f"{self.base_url}/chat/completions"

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        openai_messages = _to_openai_messages(system, messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
            "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
        }

        openai_tools = _to_openai_tools(tools)
        if openai_tools:
            payload["tools"] = openai_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(self._endpoint, json=payload, headers=headers)
            except Exception as exc:
                log.error("%s connection failed: %s", self.name, exc)
                raise ProviderError(f"{self.name} connection failed: {exc}") from exc

        if resp.status_code >= 400:
            err_body = resp.text[:400]
            log.error("%s API error %d: %s", self.name, resp.status_code, err_body)
            raise ProviderError(f"{self.name} API error {resp.status_code}: {err_body}")

        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}

        text_content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []

        parsed_tool_uses: list[ToolUse] = []
        for tc in tool_calls:
            func = tc.get("function") or {}
            fn_name = func.get("name", "")
            raw_args = func.get("arguments", "{}")
            try:
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except Exception:
                parsed_args = {}
            parsed_tool_uses.append(
                ToolUse(
                    id=tc.get("id") or f"call_{fn_name}",
                    name=fn_name,
                    input=parsed_args,
                    extra_content=tc.get("extra_content"),
                )
            )

        usage = data.get("usage") or {}
        return LLMResult(
            text=text_content.strip(),
            tool_uses=parsed_tool_uses,
            stop_reason=choice.get("finish_reason", "end_turn"),
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
            provider=self.name,
        )

    async def healthcheck(self) -> dict[str, Any]:
        try:
            res = await self.complete(
                system="",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            return {"provider": self.name, "status": "ok", "model": res.model}
        except Exception as exc:
            return {"provider": self.name, "status": "error", "detail": str(exc)}


class GeminiProvider(OpenAICompatibleProvider):
    """Google Gemini Flash model via OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        super().__init__(
            name="gemini",
            api_key=api_key or settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model=model or settings.GEMINI_MODEL,
        )


class GroqProvider(OpenAICompatibleProvider):
    """Groq LLaMA models via Groq's high-speed API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        super().__init__(
            name="groq",
            api_key=api_key or settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=model or settings.GROQ_MODEL,
        )
