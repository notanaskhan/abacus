"""Model providers (ADR-019). PROTECTED. TASK-011 design §2, Q3.

`ModelProvider` is the seam for real providers (an Anthropic provider arrives with the spec that
enables real calls; its SDK may be imported only here). SPEC-000 runs on `FakeModel`: scripted,
deterministic, local and test only.
"""

from __future__ import annotations

import hashlib
import re
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
    temperature: float | None = None  # pinned per model where accepted (the model catalog)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...


Responder = Callable[[ModelRequest], str]


_SHA256 = re.compile(r"[0-9a-f]{64}")


class FakeModel:
    """Answers each prompt with its registered responder. A prompt with none is an error.

    F-04-T19 (F-04.26): a scenario may record a response for (prompt, content hash). It is
    served before the responder when the request carries that content: the SHA-256 of the
    rendered input, or a document's SHA-256 named in it. Recorded responses are data files from
    the scenario, never model-generated. Local runs and tests only, as the class itself."""

    def __init__(self, responders: dict[str, Responder] | None = None) -> None:
        if settings().environment not in SYNTHETIC_ENVIRONMENTS:
            raise RuntimeError("FakeModel is for local runs and tests only")
        self._responders: dict[str, Responder] = dict(responders or {})
        self._recorded: dict[tuple[str, str], str] = {}

    def respond(self, prompt_ref: str, responder: Responder) -> None:
        self._responders[prompt_ref] = responder

    def record(self, prompt_ref: str, content_sha256: str, text: str) -> None:
        """A scenario's response to `prompt_ref` for this content (a 64-hex SHA-256)."""
        if not _SHA256.fullmatch(content_sha256):
            raise ValueError("a recorded response is keyed by a 64-hex SHA-256")
        self._recorded[(prompt_ref, content_sha256)] = text

    def _recorded_for(self, request: ModelRequest) -> str | None:
        if not self._recorded:
            return None
        whole = hashlib.sha256(request.user.encode()).hexdigest()
        for key in (whole, *_SHA256.findall(request.user)):
            found = self._recorded.get((request.prompt_ref, key))
            if found is not None:
                return found
        return None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        recorded = self._recorded_for(request)
        responder = self._responders.get(request.prompt_ref)
        if recorded is None and responder is None:
            raise ProviderError(f"no fake response for {request.prompt_ref}")
        text = recorded if recorded is not None else responder(request)  # type: ignore[misc]  # one of the two is set
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
