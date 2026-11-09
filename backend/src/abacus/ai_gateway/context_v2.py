"""Context builder v2 for `converse()` (P-10-T21; ADR-234 §5, ADR-051, ADR-052, ADR-055;
chapter 05 "Context builder v2"). PROTECTED.

The only way to assemble a `ConverseCall`'s context. Nine layers, always in this order, so a
turn's cacheable prefix is the same bytes every time its inputs are the same:

    instructions  the registered capability prompt (`id@vN`), never free text
    tools         the offered tools, sorted by name; descriptions are registry prompts (ADR-049)
    firm          profile, policy summary; firm instructions inside `<firm_instruction>`
    learned       approved memory items (K-05; the slot exists, empty until then)
    skill         firm procedures inside `<firm_procedure>` (K-05; empty until then)
    engagement    the graph summary; client content inside `<untrusted>` blocks
    examples
    conversation  earlier turns, compacted to the last turns plus a summary when over budget
    task          this turn's structured input; client fields inside `<untrusted>` blocks

The first seven are system blocks and tools (the cacheable prefix); conversation and task are
messages. A prompt-cache breakpoint follows the last firm-level layer (firm, learned, skill: the
same for every run of the firm) and the last system layer.

Rules the builder holds:
- **Instructions come from the registry.** `ContextV2Builder(prompt_ref, tier)` resolves the ref
  and refuses one that is not registered (`InstructionsNotRegistered`); there is no way to set
  instruction text.
- **Per-tier budgets** (input tokens, inferred and tuned by evals): small 8k, medium 32k, large
  64k. Each system layer has a share of its tier's budget and is cut at it (recorded); the task
  layer is never cut and is refused when it can't fit (`ContextTooLarge`); the conversation is
  compacted to what is left.
- **Untrusted tool results are always wrapped.** A tool result enters only through
  `tool_result_block(...)`, which renders the trusted fields as JSON and each untrusted field in
  its own `<untrusted name="…">` block, JSON-encoded with `<` escaped (ADR-052). A tool result
  block in the conversation that is not in that form is refused (`UnwrappedToolResult`).
- **Data subjects** (C19 condition 6) and evidence sources ride along, so the boundary can enforce
  §7216 and the access events without parsing text.
- **Compaction** keeps the last `KEEP_TURNS` messages (never splitting a tool call from its
  result) and replaces the rest with a summary from the registered compactor (`sessions.compactor`,
  W-02, through `register_compactor`). With none registered, the earlier turns are dropped and
  the context records it. The summary enters as a `<conversation_summary>` block.

`call()` and v1's `ContextBuilder` are untouched (AC-G6).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal, cast
from uuid import UUID

from abacus.ai_gateway.context import (
    MAX_ROWS,
    ContextTooLarge,
    DatasetTooLarge,
    DataSubject,
    estimate_tokens,
)
from abacus.ai_gateway.prompts import Prompt, UnknownPrompt, prompt
from abacus.ai_gateway.providers import (
    ConverseMessage,
    SystemBlock,
    TextBlock,
    Tier,
    ToolResultBlock,
    ToolUseBlock,
)

LayerV2 = Literal[
    "instructions",
    "tools",
    "firm",
    "learned",
    "skill",
    "engagement",
    "examples",
    "conversation",
    "task",
]
LAYERS_V2: Final[tuple[LayerV2, ...]] = (
    "instructions",
    "tools",
    "firm",
    "learned",
    "skill",
    "engagement",
    "examples",
    "conversation",
    "task",
)
SystemLayer = Literal["firm", "learned", "skill", "engagement", "examples"]
SYSTEM_LAYERS: Final[tuple[SystemLayer, ...]] = (
    "firm",
    "learned",
    "skill",
    "engagement",
    "examples",
)
_FIRM_LEVEL: Final = ("firm", "learned", "skill")
# Input tokens per tier (chapter 05; tuned by evals).
TIER_BUDGETS: Final[Mapping[Tier, int]] = {"small": 8_000, "medium": 32_000, "large": 64_000}
# Each system layer's share of its tier's budget; the rest is tools, conversation and task.
LAYER_SHARES: Final[Mapping[SystemLayer, float]] = {
    "firm": 0.05,
    "learned": 0.05,
    "skill": 0.05,
    "engagement": 0.10,
    "examples": 0.10,
}
CHARS_PER_TOKEN: Final = 4
KEEP_TURNS: Final = 6
_TAGS: Final[Mapping[SystemLayer, str]] = {
    "firm": "firm_instruction",
    "skill": "firm_procedure",
}
_NAME: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UNTRUSTED_BLOCK: Final = re.compile(
    r'^<untrusted name="([a-z][a-z0-9_]{0,63})">\n([^<]*)\n</untrusted>$'
)


class InstructionsNotRegistered(ValueError):
    """The instructions layer named a prompt the registry doesn't hold (ADR-057)."""


class UnwrappedToolResult(ValueError):
    """A tool result reached the conversation without `tool_result_block`'s wrapping."""


Compactor = Callable[[Sequence[ConverseMessage]], Awaitable[str]]
_COMPACTOR: list[Compactor] = []


def register_compactor(compactor: Compactor) -> None:
    """`sessions.compactor` (W-02): summarises the turns compaction drops. One registration."""
    if _COMPACTOR and _COMPACTOR[0] is not compactor:
        raise ValueError("a compactor is already registered")
    _COMPACTOR[:] = [compactor]


def _encode(value: object) -> str:
    """Canonical JSON with `<` escaped: an untrusted value can't open or close a block."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).replace(
        "<", "\\u003c"
    )


def _longest_list(value: object) -> int:
    if isinstance(value, list | tuple):
        items = list(cast(Collection[object], value))
        return max([len(items), *(_longest_list(v) for v in items)])
    if isinstance(value, Mapping):
        return max([0, *(_longest_list(v) for v in cast(Mapping[object, object], value).values())])
    return 0


def wrapped(data: Mapping[str, object], untrusted: Collection[str]) -> str:
    """Trusted fields as one JSON object, then each untrusted field in its own block."""
    for name in untrusted:
        if not _NAME.match(name):
            raise ValueError(f"untrusted field {name!r} is not an identifier")
    trusted = {k: v for k, v in data.items() if k not in untrusted}
    parts = [_encode(trusted)]
    for name in sorted(k for k in data if k in untrusted):
        parts.append(f'<untrusted name="{name}">\n{_encode(data[name])}\n</untrusted>')
    return "\n".join(parts)


def render_tool_result(
    name: str,
    result: Mapping[str, object] | None,
    *,
    untrusted: Collection[str],
    refused: str | None = None,
) -> str:
    """A tool's answer as the next turn reads it (AC-R5): `{"tool", "result"}` with the trusted
    fields, each untrusted field in its own block. A refusal is its code alone."""
    if refused is not None or result is None:
        return _encode({"refused": refused, "tool": name})
    trusted = {k: v for k, v in result.items() if k not in untrusted}
    head = _encode({"result": trusted, "tool": name})
    blocks = wrapped({k: v for k, v in result.items() if k in untrusted}, untrusted)
    tail = blocks.split("\n", 1)[1] if "\n" in blocks else ""
    return f"{head}\n{tail}" if tail else head


def tool_result_block(
    tool_use_id: str,
    name: str,
    result: Mapping[str, object] | None,
    *,
    untrusted: Collection[str],
    refused: str | None = None,
) -> ToolResultBlock:
    """The only way a tool result enters a conversation."""
    return ToolResultBlock(
        tool_use_id=tool_use_id,
        content=render_tool_result(name, result, untrusted=untrusted, refused=refused),
        is_error=refused is not None,
    )


def _check_tool_result(block: ToolResultBlock) -> None:
    """A tool result block is one JSON line naming the tool, then only `<untrusted>` blocks."""
    head, _, rest = block.content.partition("\n")
    try:
        parsed = cast(object, json.loads(head))
    except json.JSONDecodeError:
        raise UnwrappedToolResult(block.tool_use_id) from None
    if not isinstance(parsed, dict) or "tool" not in parsed or "<" in head:
        raise UnwrappedToolResult(block.tool_use_id)
    if not rest:
        return
    for chunk in re.split(r"\n(?=<untrusted )", rest):
        match = _UNTRUSTED_BLOCK.match(chunk)
        if match is None:
            raise UnwrappedToolResult(block.tool_use_id)
        try:
            json.loads(match.group(2))
        except json.JSONDecodeError:
            raise UnwrappedToolResult(block.tool_use_id) from None


@dataclass(frozen=True)
class OfferedTool:
    """A tool as the turn offers it: its name, rendered registry description and input schema.
    The gateway's `ConverseTool` is built from it by the caller that holds the input model."""

    name: str
    description_ref: str  # `tool.<name>@vN`
    input_schema: Mapping[str, object]


@dataclass(frozen=True)
class ContextV2:
    """An assembled v2 context: what `ConverseCall` takes, plus how it was assembled."""

    prompt: Prompt
    tier: Tier
    tools: tuple[OfferedTool, ...]
    layers: tuple[SystemBlock, ...]
    layer_names: tuple[SystemLayer, ...]
    messages: tuple[ConverseMessage, ...]
    data_subjects: tuple[DataSubject, ...]
    sources: tuple[UUID, ...]
    truncated: tuple[LayerV2, ...] = ()
    compacted: bool = False
    dropped_turns: int = 0

    def prefix(self) -> bytes:
        """The cacheable prefix: instructions, tools and system layers, byte-for-byte."""
        doc = {
            "instructions": {"ref": self.prompt.ref, "sha256": self.prompt.sha256},
            "tools": [
                {"description": t.description_ref, "name": t.name, "schema": t.input_schema}
                for t in self.tools
            ],
            "layers": [
                {"cache": b.cache, "name": n, "text": b.text}
                for n, b in zip(self.layer_names, self.layers, strict=True)
            ],
        }
        return json.dumps(doc, sort_keys=True, ensure_ascii=False, default=str).encode()

    @property
    def prefix_sha256(self) -> str:
        return hashlib.sha256(self.prefix()).hexdigest()

    def tokens(self) -> int:
        texts = [self.prompt.text, *(b.text for b in self.layers)]
        texts += [json.dumps(t.input_schema, default=str) for t in self.tools]
        texts += [_message_text(m) for m in self.messages]
        return sum(estimate_tokens(t) for t in texts)


def _message_text(message: ConverseMessage) -> str:
    out: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            out.append(block.text)
        elif isinstance(block, ToolResultBlock):
            out.append(block.content)
        elif isinstance(block, ToolUseBlock):
            out.append(json.dumps(dict(block.input), sort_keys=True, default=str))
    return "\n".join(out)


def _tokens(messages: Sequence[ConverseMessage]) -> int:
    return sum(estimate_tokens(_message_text(m)) for m in messages)


def _safe_start(messages: Sequence[ConverseMessage], start: int) -> int:
    """The first index at or after `start` where the kept turns can begin: a user message that
    answers no tool call it would lose."""
    while start < len(messages):
        m = messages[start]
        if m.role == "user" and not any(isinstance(b, ToolResultBlock) for b in m.content):
            return start
        start += 1
    return start


@dataclass
class ContextV2Builder:
    prompt_ref: str
    tier: Tier
    _prompt: Prompt | None = None
    _tools: dict[str, OfferedTool] = field(default_factory=dict[str, OfferedTool])
    _texts: dict[SystemLayer, str] = field(default_factory=dict[SystemLayer, str])
    _conversation: tuple[ConverseMessage, ...] = ()
    _task: str | None = None
    _subjects: tuple[DataSubject, ...] = ()
    _sources: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if self.tier not in TIER_BUDGETS:
            raise ValueError(f"unknown tier {self.tier!r}")
        try:
            self._prompt = prompt(self.prompt_ref)
        except UnknownPrompt:
            raise InstructionsNotRegistered(self.prompt_ref) from None

    @property
    def budget(self) -> int:
        return TIER_BUDGETS[self.tier]

    def text(self, layer: LayerV2, text: str) -> ContextV2Builder:
        """A system layer's text. Instructions, tools, conversation and task have their own
        methods; instructions have none that takes text."""
        if layer == "instructions":
            raise InstructionsNotRegistered("instructions come from the prompt registry")
        if layer not in SYSTEM_LAYERS:
            raise ValueError(f"{layer} is not a text layer")
        tag = _TAGS.get(layer)
        self._texts[layer] = f"<{tag}>\n{text}\n</{tag}>" if tag and text else text
        return self

    def engagement(
        self, data: Mapping[str, object], *, untrusted: Collection[str]
    ) -> ContextV2Builder:
        """The engagement summary as structured data; client fields in `<untrusted>` blocks."""
        if _longest_list(data) > MAX_ROWS:
            raise DatasetTooLarge(f"lists are limited to {MAX_ROWS} rows")
        self._texts["engagement"] = wrapped(data, untrusted)
        return self

    def learned(self, items: Sequence[str]) -> ContextV2Builder:
        """Approved memory items (K-05), one per line, in the order given."""
        self._texts["learned"] = "\n".join(f"- {i}" for i in items)
        return self

    def tools(self, *offered: OfferedTool) -> ContextV2Builder:
        for t in offered:
            if not t.description_ref.startswith(f"tool.{t.name}@v"):
                raise ValueError(f"tool {t.name!r}: its description is a registry prompt")
            if t.name in self._tools and self._tools[t.name] != t:
                raise ValueError(f"tool {t.name!r} is offered twice")
            self._tools[t.name] = t
        return self

    def conversation(self, *messages: ConverseMessage) -> ContextV2Builder:
        for m in messages:
            for block in m.content:
                if isinstance(block, ToolResultBlock):
                    _check_tool_result(block)
        self._conversation = (*self._conversation, *messages)
        return self

    def task(self, data: Mapping[str, object], *, untrusted: Collection[str]) -> ContextV2Builder:
        if _longest_list(data) > MAX_ROWS:
            raise DatasetTooLarge(f"task input lists are limited to {MAX_ROWS} rows")
        self._task = wrapped(data, untrusted)
        return self

    def subjects(self, *subjects: DataSubject) -> ContextV2Builder:
        self._subjects = tuple(dict.fromkeys((*self._subjects, *subjects)))
        return self

    def sources(self, *evidence_version_ids: UUID) -> ContextV2Builder:
        self._sources = tuple(dict.fromkeys((*self._sources, *evidence_version_ids)))
        return self

    def _system(self) -> tuple[tuple[SystemBlock, ...], tuple[SystemLayer, ...], list[LayerV2]]:
        names: list[SystemLayer] = [n for n in SYSTEM_LAYERS if self._texts.get(n)]
        truncated: list[LayerV2] = []
        texts: list[str] = []
        for name in names:
            limit = int(self.budget * LAYER_SHARES[name]) * CHARS_PER_TOKEN
            text = self._texts[name]
            if len(text) > limit:
                text = text[:limit]
                truncated.append(name)
            texts.append(text)
        firm_last = max((i for i, n in enumerate(names) if n in _FIRM_LEVEL), default=-1)
        blocks = tuple(
            SystemBlock(text, cache=(i == firm_last or i == len(names) - 1))
            for i, text in enumerate(texts)
        )
        return blocks, tuple(names), truncated

    async def build(self) -> ContextV2:
        if self._task is None:
            raise ValueError("a turn has a task")
        found = cast(Prompt, self._prompt)
        blocks, names, truncated = self._system()
        tools = tuple(self._tools[n] for n in sorted(self._tools))
        task = ConverseMessage("user", (TextBlock(self._task),))
        base = ContextV2(found, self.tier, tools, blocks, names, (task,), self._subjects,
                         self._sources, tuple(truncated))  # fmt: skip
        if base.tokens() > self.budget:
            raise ContextTooLarge("the task does not fit its tier's budget")
        room = self.budget - base.tokens()
        turns = list(self._conversation)
        compacted, dropped = False, 0
        if _tokens(turns) > room:
            start = _safe_start(turns, max(0, len(turns) - KEEP_TURNS))
            older, turns = turns[:start], turns[start:]
            while turns and _tokens(turns) > room:  # the last turns alone are over: drop more
                start = _safe_start(turns, 1)
                older, turns = older + turns[:start], turns[start:]
            dropped = len(older)
            compacted = True
            if older and _COMPACTOR:
                summary = await _COMPACTOR[0](older)
                block = TextBlock(
                    f"<conversation_summary>\n{_encode(summary)}\n</conversation_summary>"
                )
                head = ConverseMessage("user", (block,))
                if _tokens([head, *turns]) <= room:
                    turns = [head, *turns]
        messages = _merged((*turns, task))
        return replace(base, messages=messages, compacted=compacted, dropped_turns=dropped)


def _merged(messages: Sequence[ConverseMessage]) -> tuple[ConverseMessage, ...]:
    """Adjacent messages of the same role joined, so the turns alternate as providers require."""
    out: list[ConverseMessage] = []
    for m in messages:
        if out and out[-1].role == m.role:
            out[-1] = ConverseMessage(m.role, (*out[-1].content, *m.content))
        else:
            out.append(m)
    return tuple(out)
