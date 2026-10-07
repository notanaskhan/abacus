"""Model providers (ADR-019). PROTECTED. TASK-011 design §2, Q3.

`ModelProvider` is the seam for real providers (an Anthropic provider arrives with the spec that
enables real calls; its SDK may be imported only here). SPEC-000 runs on `FakeModel`: scripted,
deterministic, local and test only.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from abacus.kernel.config import SYNTHETIC_ENVIRONMENTS, settings

Tier = Literal["small", "medium", "large"]


class ProviderError(Exception):
    """The provider failed (network, outage, refusal). Retryable by the caller's workflow. A
    rate-limit response (HTTP 429 or the provider's equivalent) sets `rate_limited`, with the wait
    the provider asked for, if any: the gateway then stops admitting calls to that model
    (ADR-072)."""

    def __init__(
        self,
        message: str = "",
        *,
        rate_limited: bool = False,
        retry_after: float | None = None,
        auth: bool = False,
    ) -> None:
        super().__init__(message)
        self.rate_limited = rate_limited
        self.retry_after = retry_after
        # SPEC-010 Q3: credentials refused (401/403). Not an outage: the route isn't blocked, the
        # attempt fails over, and operators are alerted.
        self.auth = auth


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    user: str
    max_output_tokens: int
    prompt_ref: str


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


Responder = Callable[[ModelRequest], str]


class FakeModel:
    """Answers each prompt with its registered responder. A prompt with none is an error."""

    def __init__(self, responders: dict[str, Responder] | None = None) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("FakeModel is for local runs and tests only")
        self._responders: dict[str, Responder] = dict(responders or {})

    def respond(self, prompt_ref: str, responder: Responder) -> None:
        self._responders[prompt_ref] = responder

    async def complete(self, request: ModelRequest) -> ModelResponse:
        responder = self._responders.get(request.prompt_ref)
        if responder is None:
            raise ProviderError(f"no fake response for {request.prompt_ref}")
        text = responder(request)
        return ModelResponse(
            text=text,
            input_tokens=(len(request.system) + len(request.user)) // 4,
            output_tokens=len(text) // 4,
            model=request.model,
        )


_provider: ModelProvider | None = None


def configure_provider(provider: ModelProvider | None) -> None:
    global _provider
    _provider = provider


def provider() -> ModelProvider:
    if _provider is None:
        raise RuntimeError("no model provider configured")
    return _provider
