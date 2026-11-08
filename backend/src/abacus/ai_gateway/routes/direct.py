"""The direct route: the provider's own Messages API (SPEC-010). PROTECTED."""

from __future__ import annotations

from typing import cast

import anthropic
from anthropic.types import Message

from abacus.ai_gateway.providers import (
    ConverseRequest,
    ConverseResponse,
    ModelRequest,
    ModelResponse,
)
from abacus.ai_gateway.routes._anthropic import (
    converse_args,
    message_args,
    to_converse_response,
    to_error,
    to_response,
)
from abacus.kernel.config import settings


class AnthropicDirect:
    def __init__(self, client: anthropic.AsyncAnthropic | None = None) -> None:
        if client is None:
            key = settings().anthropic_api_key
            if key is None:
                raise RuntimeError("the direct route needs anthropic_api_key")
            # Retries are the gateway's (attempts, failover), never the SDK's.
            client = anthropic.AsyncAnthropic(api_key=key.get_secret_value(), max_retries=0)
        self._client = client

    async def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            message = cast(Message, await self._client.messages.create(**message_args(request)))
        except Exception as exc:
            raise to_error(exc) from None
        return to_response(message, request.model)

    async def converse(self, request: ConverseRequest) -> ConverseResponse:
        """Seam v2 (P-10-T12): one non-streaming turn with tools; never retried by the SDK."""
        try:
            message = cast(Message, await self._client.messages.create(**converse_args(request)))
        except Exception as exc:
            raise to_error(exc) from None
        return to_converse_response(message, request.model)
