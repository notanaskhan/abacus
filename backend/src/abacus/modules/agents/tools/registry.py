"""C17: narrow, typed agent tools (P-10-T10 stub; ADR-233, ADR-049; SPEC-647 AC-R1 to AC-R8).
PROTECTED. Contract: `docs/contracts/tool-registry.md`.

Tools live in the module that owns the data (`modules/<m>/agent_tools.py`) and register through
this slot (ADR-106), so module import rules hold. An unregistered tool fails closed: a spec naming
one fails codegen, a run calling one gets `tool_not_registered`.

There are four kinds, and a final verb (approve, sign off, release, send, post, export, transmit,
decide, publish, adopt, resolve, accept, reject) can only be `approved_write`: TOOL-001 reads the
decorator, `abacus_tools.quality.tool_registry` reads the registry, and `register_tool` itself
refuses. An `approved_write` tool's matrix action must be `agent: deny`, since it runs only under a
person's approval grant. There is no generic query tool.

The harness that calls a tool (per-call authorisation, scope pinning, §7216, idempotency key
`(run_id, step_seq, attempt)`, `<untrusted>` wrapping) lands with P-10-T17 and T21.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Final, Literal, TypeVar

from pydantic import BaseModel

from abacus.kernel.errors import DomainConflict

ToolKind = Literal["read", "compute", "propose", "approved_write"]
DataClass = Literal["internal", "confidential", "restricted", "tri"]
# What a tool answers instead of a result; the model reads the code, never a row about the refusal.
ToolRefusal = Literal[
    "consent_required", "not_visible", "out_of_scope", "row_limit", "stale_source", "no_grant"
]
TOOL_KINDS: Final = frozenset({"read", "compute", "propose", "approved_write"})
MAX_ROWS: Final = 200
# I-AGENT-NEVER's verbs as they appear in an action or a tool name.
_VERBS: Final = (
    "approve sign_off signoff release send post export transmit decide publish adopt resolve "
    "accept reject"
)
NEVER_TOOL_VERBS: Final = frozenset(_VERBS.split())
_NAME: Final = re.compile(r"^[a-z][a-z_]*\.[a-z][a-z_]*$")


class ToolNotRegistered(DomainConflict):
    code = "tool_not_registered"


class ToolInvalid(ValueError):
    """A tool that breaks C17's rules; raised at import, so it can't ship."""


@dataclass(frozen=True)
class AgentTool:
    """What a tool is. `description` is `tool.<name>@v<n>`, a registry prompt (ADR-234)."""

    name: str
    kind: ToolKind
    action: str
    description: str
    data_class: DataClass
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Awaitable[BaseModel]]
    untrusted: tuple[str, ...] = ()
    max_rows: int = MAX_ROWS
    paginate: bool = False
    records_read: str | None = None


def has_never_verb(text: str) -> bool:
    """Whether an action or tool name holds a final verb, as a whole `_` or `.` separated word or
    the two-word `sign_off`."""
    words = re.split(r"[._]", text)
    pairs = {f"{a}_{b}" for a, b in pairwise(words)}
    return bool((set(words) | pairs) & NEVER_TOOL_VERBS)


_TOOLS: dict[str, AgentTool] = {}


def validate_tool(tool: AgentTool) -> None:
    if not _NAME.match(tool.name):
        raise ToolInvalid(f"tool {tool.name!r}: a name is <module>.<verb_noun>")
    if tool.kind not in TOOL_KINDS:
        raise ToolInvalid(f"tool {tool.name!r}: unknown kind {tool.kind!r}")
    if tool.kind != "approved_write" and (
        has_never_verb(tool.action) or has_never_verb(tool.name)
    ):
        raise ToolInvalid(
            f"tool {tool.name!r}: a final verb can only be approved_write (TOOL-001)"
        )
    if tool.max_rows > MAX_ROWS:
        raise ToolInvalid(f"tool {tool.name!r}: at most {MAX_ROWS} rows (ADR-049)")
    if tool.description != f"tool.{tool.name}@v1" and not tool.description.startswith(
        f"tool.{tool.name}@v"
    ):
        raise ToolInvalid(f"tool {tool.name!r}: its description is a registry prompt")


def register_tool(tool: AgentTool) -> None:
    validate_tool(tool)
    existing = _TOOLS.get(tool.name)
    if existing is not None and existing.handler is not tool.handler:
        raise ToolInvalid(f"tool {tool.name!r} is already registered")
    _TOOLS[tool.name] = tool


def registered_tools() -> Mapping[str, AgentTool]:
    return dict(_TOOLS)


def tool(name: str) -> AgentTool:
    """Fail closed: a name no module registered answers `tool_not_registered`."""
    found = _TOOLS.get(name)
    if found is None:
        raise ToolNotRegistered(name)
    return found


def unregistered(names: Iterable[str]) -> list[str]:
    """For spec v2's codegen (P-10-T16): the names a spec holds that no module registered."""
    return sorted(set(names) - set(_TOOLS))


Handler = TypeVar("Handler", bound=Callable[..., Awaitable[BaseModel]])


def agent_tool(
    *,
    name: str,
    kind: ToolKind,
    action: str,
    data_class: DataClass,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    untrusted: tuple[str, ...] = (),
    max_rows: int = MAX_ROWS,
    paginate: bool = False,
    records_read: str | None = None,
    description: str | None = None,
) -> Callable[[Handler], Handler]:
    """Declare a tool on its handler `async def f(agent: AgentContext, args: In) -> Out`."""

    def register(handler: Handler) -> Handler:
        register_tool(
            AgentTool(
                name=name,
                kind=kind,
                action=action,
                description=description or f"tool.{name}@v1",
                data_class=data_class,
                input_model=input_model,
                output_model=output_model,
                handler=handler,
                untrusted=untrusted,
                max_rows=max_rows,
                paginate=paginate,
                records_read=records_read,
            )
        )
        return handler

    return register
