"""Shared request and error mapping for the Anthropic Messages API on both routes (SPEC-010).
The system prompt is sent as a cached block (prompt caching, a parity feature); cache reads and
writes count as input tokens. Errors become `ProviderError`: 429 rate-limited (with its wait),
401/403 auth, and anything else (5xx, 529, timeouts, connection) an outage."""

from __future__ import annotations

from typing import Any

import anthropic
from anthropic.types import Message, TextBlock
from anthropic.types import ToolUseBlock as SdkToolUseBlock

from abacus.ai_gateway import providers as p
from abacus.ai_gateway.providers import ModelRequest, ModelResponse, ProviderError


def message_args(request: ModelRequest) -> dict[str, Any]:  # SDK keyword arguments, mixed types
    args: dict[str, Any] = {  # SDK keyword arguments, mixed types
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "system": [
            {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [{"role": "user", "content": request.user}],
    }
    if request.temperature is not None:
        # The SDK no longer names sampling parameters; models that still accept one take it in
        # the request body (the catalog pins it only for those).
        args["extra_body"] = {"temperature": request.temperature}
    return args


def to_response(message: Message, model: str) -> ModelResponse:
    text = "".join(block.text for block in message.content if isinstance(block, TextBlock))
    usage = message.usage
    cached = (getattr(usage, "cache_read_input_tokens", 0) or 0) + (
        getattr(usage, "cache_creation_input_tokens", 0) or 0
    )
    return ModelResponse(
        text=text,
        input_tokens=int(usage.input_tokens) + int(cached),
        output_tokens=int(usage.output_tokens),
        model=model,
    )


# --- Seam v2 (P-10-T12; ADR-234) ------------------------------------------------------------
# `message_args` and `to_response` above serve `complete()` and are unchanged (AC-G6).

_EPHEMERAL: dict[str, str] = {"type": "ephemeral"}
# The provider's stop reasons, in the gateway's words. `stop_sequence` is a finished turn (the
# gateway sets none); `pause_turn` (server tools, never offered) and a context overflow are
# provider errors, so the attempt fails over or the harness escalates.
_STOP: dict[str, p.StopReason] = {
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


def _block(block: p.ContentBlock) -> dict[str, Any]:  # SDK content block params
    if isinstance(block, p.TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, p.ToolUseBlock):
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)}
    if isinstance(block, p.ToolResultBlock):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
            "is_error": block.is_error,
        }
    document: dict[str, Any] = {  # SDK JSON payload
        "type": "document",
        "source": {"type": "base64", "media_type": block.media_type, "data": block.data_base64},
    }
    if block.title is not None:
        document["title"] = block.title
    return document


def converse_args(request: p.ConverseRequest) -> dict[str, Any]:  # SDK keyword arguments
    system: list[dict[str, Any]] = []  # SDK JSON payload
    for layer in request.system_blocks:
        item: dict[str, Any] = {"type": "text", "text": layer.text}  # SDK JSON payload
        if layer.cache:
            item["cache_control"] = dict(_EPHEMERAL)
        system.append(item)
    args: dict[str, Any] = {  # SDK JSON payload
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "system": system,
        "messages": [
            {"role": m.role, "content": [_block(b) for b in m.content]} for m in request.messages
        ],
    }
    if request.tools:
        tools: list[dict[str, Any]] = [  # SDK JSON payload
            {"name": t.name, "description": t.description, "input_schema": dict(t.input_schema)}
            for t in request.tools
        ]
        if request.cache_tools:
            tools[-1]["cache_control"] = dict(_EPHEMERAL)
        args["tools"] = tools
        args["tool_choice"] = {"type": request.tool_choice}
    elif request.tool_choice == "any":
        raise ValueError("tool_choice any needs at least one tool")
    if request.temperature is not None:
        args["extra_body"] = {"temperature": request.temperature}
    return args


def to_converse_response(message: Message, model: str) -> p.ConverseResponse:
    stop = _STOP.get(str(message.stop_reason))
    if stop is None:
        raise ProviderError(f"stop {message.stop_reason}")
    blocks: list[p.TextBlock | p.ToolUseBlock] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            blocks.append(p.TextBlock(block.text))
        elif isinstance(block, SdkToolUseBlock):
            blocks.append(p.ToolUseBlock(block.id, block.name, dict(block.input)))
        # thinking and server-tool blocks are never requested; anything else is dropped
    usage = message.usage
    return p.ConverseResponse(
        content_blocks=tuple(blocks),
        stop_reason=stop,
        input_tokens=int(usage.input_tokens),
        output_tokens=int(usage.output_tokens),
        cache_read_tokens=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
        cache_write_tokens=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        model=model,
    )


def to_error(exc: Exception) -> ProviderError:
    """Class names and status only: never the provider's message (it may echo the prompt)."""
    if isinstance(exc, anthropic.RateLimitError):
        after = exc.response.headers.get("retry-after")
        try:
            wait = float(after) if after is not None else None
        except ValueError:
            wait = None
        return ProviderError("rate_limited", rate_limited=True, retry_after=wait)
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ProviderError("auth", auth=True)
    if isinstance(exc, anthropic.APIStatusError):
        return ProviderError(f"status {exc.status_code}")
    return ProviderError(type(exc).__name__)
