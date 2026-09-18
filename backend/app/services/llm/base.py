"""Provider-agnostic LLM interface.

The message/content-block shape mirrors the Anthropic Messages API because it
is the richest of the common formats (text + tool_use + tool_result blocks);
other providers can be adapted to it without loss.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(slots=True)
class ToolUse:
    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    extra_content: dict[str, Any] | None = None


@dataclass(slots=True)
class LLMResult:
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)
    stop_reason: str = "end_turn"
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    provider: str = ""

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_uses)


class BaseLLMProvider(abc.ABC):
    """Every LLM backend implements this one method."""

    name: str = "base"

    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[ToolSpec] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        """Return the next assistant turn (text and/or tool calls)."""

    async def healthcheck(self) -> dict[str, Any]:
        return {"provider": self.name, "status": "ok"}


# --------------------------------------------------------------------------
# Small helpers shared by providers
# --------------------------------------------------------------------------
def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def user_message(text: str) -> dict[str, Any]:
    return {"role": "user", "content": [text_block(text)]}


def assistant_message(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {"role": "assistant", "content": blocks}


def tool_result_message(tool_use_id: str, content: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            }
        ],
    }


def last_user_text(messages: list[dict[str, Any]]) -> str:
    """Most recent plain-text user utterance (ignores tool_result turns)."""
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        for block in content or []:
            if block.get("type") == "text":
                return block.get("text", "")
    return ""
