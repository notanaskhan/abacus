"""Shared request and error mapping for the Anthropic Messages API on both routes (SPEC-010).
The system prompt is sent as a cached block (prompt caching, a parity feature); cache reads and
writes count as input tokens. Errors become `ProviderError`: 429 rate-limited (with its wait),
401/403 auth, and anything else (5xx, 529, timeouts, connection) an outage."""

from __future__ import annotations

from typing import Any

import anthropic
from anthropic.types import Message, TextBlock

from abacus.ai_gateway.providers import ModelRequest, ModelResponse, ProviderError


def message_args(request: ModelRequest) -> dict[str, Any]:  # SDK keyword arguments, mixed types
    return {
        "model": request.model,
        "max_tokens": request.max_output_tokens,
        "system": [
            {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [{"role": "user", "content": request.user}],
    }


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
