"""Model providers (ADR-019). PROTECTED. TASK-011 design §2, Q3.

`ModelProvider` is the seam for real providers (an Anthropic provider arrives with the spec that
enables real calls; its SDK may be imported only here). SPEC-000 runs on `FakeModel`: scripted,
deterministic, local and test only.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

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


# --- Seam v2: conversations with tool use (P-10-T12; ADR-234; chapter 05 §5.3.2) -------------
# Additive: `ModelRequest`, `ModelResponse` and `complete()` above are unchanged, so `call()` and
# every specialist on it replay byte-identically (AC-G6). `converse()` is a second method with its
# own request and response types. Nothing here streams (AC-G7).

StopReason = Literal["tool_use", "end_turn", "max_tokens", "refusal"]
ToolChoice = Literal["auto", "none", "any"]


@dataclass(frozen=True)
class TextBlock:
    text: str
    type: Literal["text"] = "text"


@dataclass(frozen=True)
class ToolUseBlock:
    """The model asks for a tool. `input` is unvalidated until the harness checks it against the
    tool's input schema (AC-G4); nothing executes from this block alone."""

    id: str
    name: str
    input: Mapping[str, object]
    type: Literal["tool_use"] = "tool_use"


@dataclass(frozen=True)
class ToolResultBlock:
    """A tool's answer, sent back on the next user turn. `content` is the tool's serialised
    output (client content inside it is already wrapped in `<untrusted>`, ADR-052)."""

    tool_use_id: str
    content: str
    is_error: bool = False
    type: Literal["tool_result"] = "tool_result"


@dataclass(frozen=True)
class DocumentBlock:
    """A PDF handed to the model whole (route parity `documents`). Base64 data, never a URL."""

    data_base64: str
    title: str | None = None
    media_type: Literal["application/pdf"] = "application/pdf"
    type: Literal["document"] = "document"


ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock | DocumentBlock


@dataclass(frozen=True)
class ConverseMessage:
    role: Literal["user", "assistant"]
    content: tuple[ContentBlock, ...]


@dataclass(frozen=True)
class SystemBlock:
    """One layer of the system prompt. `cache` marks a prompt-cache breakpoint after this block
    (the fixed layer order of ADR-234 §5: instructions, tools, firm, engagement, examples)."""

    text: str
    cache: bool = False


@dataclass(frozen=True)
class ToolSpec:
    """A tool as the provider sees it. `description` is the rendered registry prompt
    (`tool.<module>.<name>@vN`, ADR-049); `input_schema` is JSON Schema."""

    name: str
    description: str
    input_schema: Mapping[str, object]


@dataclass(frozen=True)
class ConverseRequest:
    model: str
    system_blocks: tuple[SystemBlock, ...]
    messages: tuple[ConverseMessage, ...]
    max_output_tokens: int
    prompt_ref: str
    tools: tuple[ToolSpec, ...] = ()
    tool_choice: ToolChoice = "auto"
    cache_tools: bool = True  # a cache breakpoint after the last tool definition
    temperature: float | None = None


@dataclass(frozen=True)
class ConverseResponse:
    """`input_tokens` excludes cached input; cache reads and writes are counted apart so the
    gateway prices them as the catalog says."""

    content_blocks: tuple[TextBlock | ToolUseBlock, ...]
    stop_reason: StopReason
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str

    @property
    def text(self) -> str:
        return "".join(b.text for b in self.content_blocks if isinstance(b, TextBlock))

    @property
    def tool_uses(self) -> tuple[ToolUseBlock, ...]:
        return tuple(b for b in self.content_blocks if isinstance(b, ToolUseBlock))


@runtime_checkable
class ConversingProvider(Protocol):
    async def converse(self, request: ConverseRequest) -> ConverseResponse: ...


@dataclass(frozen=True)
class ToolCallTurn:
    """A scripted assistant turn asking for tools: (name, input) pairs, in order."""

    calls: tuple[tuple[str, Mapping[str, object]], ...]
    text: str = ""


@dataclass(frozen=True)
class FinalTurn:
    """A scripted assistant turn ending the conversation (`end_turn`), usually the JSON of the
    call's final schema; `stop_reason` may be `max_tokens` or `refusal` to script those paths."""

    text: str
    stop_reason: Literal["end_turn", "max_tokens", "refusal"] = "end_turn"


ScriptTurn = ToolCallTurn | FinalTurn


@dataclass(frozen=True)
class Trajectory:
    """A FakeModel conversation script (chapter 05 §5.3.2). The turn served is the count of
    assistant messages already in the request, so a replay of the same messages gets the same
    turn: deterministic and stateless. Tool-use ids derive from the prompt, turn and position."""

    turns: tuple[ScriptTurn, ...] = field(default_factory=tuple)


def _usage_estimate(request: ConverseRequest, text: str) -> tuple[int, int, int, int]:
    """Deterministic token counts for the fake: cached system text reads from cache after the
    first turn, the rest is input."""
    cached = sum(len(b.text) for b in request.system_blocks if b.cache) // 4
    plain = sum(len(b.text) for b in request.system_blocks if not b.cache)
    for message in request.messages:
        for block in message.content:
            if isinstance(block, TextBlock):
                plain += len(block.text)
            elif isinstance(block, ToolResultBlock):
                plain += len(block.content)
            elif isinstance(block, ToolUseBlock):
                plain += len(block.name) + len(repr(sorted(block.input.items())))
            else:
                plain += len(block.data_base64) // 8
    first = not any(m.role == "assistant" for m in request.messages)
    return plain // 4, len(text) // 4, 0 if first else cached, cached if first else 0


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
        self._trajectories: dict[str, Trajectory] = {}

    def script(self, prompt_ref: str, turns: Sequence[ScriptTurn]) -> None:
        """P-10-T12: the conversation `converse()` replays for `prompt_ref`."""
        self._trajectories[prompt_ref] = Trajectory(tuple(turns))

    def scripts(self, prompt_ref: str) -> bool:
        return prompt_ref in self._trajectories

    async def converse(self, request: ConverseRequest) -> ConverseResponse:
        trajectory = self._trajectories.get(request.prompt_ref)
        if trajectory is None:
            raise ProviderError(f"no fake trajectory for {request.prompt_ref}")
        index = sum(1 for m in request.messages if m.role == "assistant")
        if index >= len(trajectory.turns):
            raise ProviderError(f"trajectory for {request.prompt_ref} has no turn {index + 1}")
        turn = trajectory.turns[index]
        blocks: list[TextBlock | ToolUseBlock] = []
        if isinstance(turn, FinalTurn):
            blocks.append(TextBlock(turn.text))
            stop: StopReason = turn.stop_reason
        else:
            if request.tool_choice == "none":
                raise ProviderError("the script asks for a tool but tool_choice is none")
            if turn.text:
                blocks.append(TextBlock(turn.text))
            offered = {t.name for t in request.tools}
            for position, (name, arguments) in enumerate(turn.calls):
                if name not in offered:
                    raise ProviderError(f"the script calls {name}, which was not offered")
                seed = f"{request.prompt_ref}|{index}|{position}|{name}".encode()
                tool_id = "toolu_fake_" + hashlib.sha256(seed).hexdigest()[:20]
                blocks.append(ToolUseBlock(tool_id, name, dict(arguments)))
            stop = "tool_use"
        text = "".join(b.text for b in blocks if isinstance(b, TextBlock))
        tokens_in, tokens_out, read, write = _usage_estimate(request, text)
        return ConverseResponse(
            content_blocks=tuple(blocks),
            stop_reason=stop,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            cache_read_tokens=read,
            cache_write_tokens=write,
            model=request.model,
        )

    def respond(self, prompt_ref: str, responder: Responder) -> None:
        self._responders[prompt_ref] = responder

    def responds(self, prompt_ref: str) -> bool:
        """A responder answers `prompt_ref` (a recorded response answers only its content)."""
        return prompt_ref in self._responders

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


def fake_responds(prompt_ref: str) -> bool:
    """P-06-T21: the configured provider is the fake model and a responder answers `prompt_ref`."""
    return isinstance(_provider, FakeModel) and _provider.responds(prompt_ref)


def provider() -> ModelProvider:
    if _provider is None:
        raise RuntimeError("no model provider configured")
    return _provider


def conversing(provider_: ModelProvider) -> ConversingProvider:
    """The provider's `converse()`, or a refusal: a route without seam v2 never takes a loop."""
    if not isinstance(provider_, ConversingProvider):
        raise ProviderError("this provider cannot converse")
    return provider_
