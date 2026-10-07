"""The Bedrock route: the same models through Amazon Bedrock in our AWS account (SPEC-010), and
Titan Text Embeddings v2 (Q5). PROTECTED. Credentials come from the task's IAM role."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Protocol, cast

import boto3
from anthropic.lib.bedrock import AsyncAnthropicBedrock
from anthropic.types import Message

from abacus.ai_gateway.embeddings import EmbeddingResponse
from abacus.ai_gateway.providers import ModelRequest, ModelResponse, ProviderError
from abacus.ai_gateway.routes._anthropic import message_args, to_error, to_response
from abacus.kernel.config import settings

TITAN: str = "amazon.titan-embed-text-v2:0"


class AnthropicOnBedrock:
    def __init__(self, client: AsyncAnthropicBedrock | None = None) -> None:
        self._client = client or AsyncAnthropicBedrock(
            aws_region=settings().bedrock_region, max_retries=0
        )

    async def complete(self, request: ModelRequest) -> ModelResponse:
        try:
            message = cast(Message, await self._client.messages.create(**message_args(request)))
        except Exception as exc:
            raise to_error(exc) from None
        return to_response(message, request.model)


class _Runtime(Protocol):
    def invoke_model(self, *, modelId: str, body: str) -> Mapping[str, object]: ...


class _Body(Protocol):
    def read(self) -> bytes: ...


class BedrockTitanEmbedder:
    """One text per request (Titan v2 takes a single input), normalised, 1,024 dimensions."""

    def __init__(self, client: _Runtime | None = None) -> None:
        self._client = client or cast(
            _Runtime,
            boto3.client(  # pyright: ignore[reportUnknownMemberType] -- untyped boto3 factory
                "bedrock-runtime", region_name=settings().bedrock_region
            ),
        )

    def _one(self, text: str) -> tuple[tuple[float, ...], int]:
        body = json.dumps(
            {"inputText": text, "dimensions": settings().embedding_dimensions, "normalize": True}
        )
        try:
            response = self._client.invoke_model(modelId=TITAN, body=body)
            payload = cast(dict[str, object], json.loads(cast(_Body, response["body"]).read()))
        except Exception as exc:
            status = _status(exc)
            if status == 429:
                raise ProviderError("rate_limited", rate_limited=True) from None
            if status in (401, 403):
                raise ProviderError("auth", auth=True) from None
            raise ProviderError(type(exc).__name__) from None
        vector = cast(list[float], payload["embedding"])
        return tuple(float(v) for v in vector), int(cast(int, payload["inputTextTokenCount"]))

    async def embed(self, model: str, texts: tuple[str, ...]) -> EmbeddingResponse:
        results = [await asyncio.to_thread(self._one, text) for text in texts]
        return EmbeddingResponse(tuple(v for v, _ in results), sum(t for _, t in results))


def _status(exc: Exception) -> int | None:
    """The HTTP status of a botocore `ClientError`, if any."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return None
    metadata = cast(dict[str, object], response).get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return None
    status = cast(dict[str, object], metadata).get("HTTPStatusCode")
    return status if isinstance(status, int) else None
