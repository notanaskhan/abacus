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

The runtime that calls a tool (per-call authorisation, scope pinning, §7216, idempotency key
`(run_id, step_seq, attempt)`, `<untrusted>` wrapping, records read and access events) is
`tools/runtime.py` (P-10-T22). C17 v1 is frozen with it
(`backend/tests/contracts/c17_tools/v1.json`).

Shapes `validate_tool` holds, so the runtime can rely on them (P-10-T22, SPEC-647 AC-R6):
- a read tool's rows are lists of models that carry an `id`, at most `max_rows` long;
- a paginated tool takes `ToolPageIn` and answers `ToolPageOut` (a cursor and code's `total`);
- `untrusted` names fields of the output model;
- a `propose` or `approved_write` tool answers identifiers and states only (no free text), because
  its answer is kept for the idempotency key's replay.
"""

from __future__ import annotations

import enum
import re
import types
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Final, Literal, TypeVar, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
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


class ToolPageIn(BaseModel):
    """What a paginated tool takes (AC-R6): an opaque cursor from the last page, and a page size of
    at most 200. Code reads past the page; the model never sees the rows it didn't ask for."""

    model_config = ConfigDict(extra="forbid")

    cursor: Annotated[str | None, Field(max_length=200), classified("internal")] = None
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS), classified("internal")] = 50


class ToolPageOut(BaseModel):
    """What a paginated tool answers beside its rows: the next page's cursor (None on the last)
    and the total, counted by code (ADR-050), never by the model."""

    next_cursor: Annotated[str | None, classified("internal")] = None
    total: Annotated[int, Field(ge=0), classified("internal")]


_SCALARS: Final = (UUID, int, bool, datetime, date, Decimal)
# A text field a write may answer: an identifier, a code or a state word, by its name.
_ID_NAME: Final = re.compile(r"^(id|.*_(id|ids|ref|refs|code|codes|key)|state|status|kind)$")


def _identifier_only(annotation: object, name: str = "") -> bool:
    """Whether a field's type holds no free text: identifiers, numbers, dates, flags, enums,
    literals, text named as an identifier, code or state, models built only of those, and lists
    or optionals of them."""
    if annotation is type(None):
        return True
    origin = get_origin(annotation)
    if origin is Literal:
        return True
    if origin is Annotated:
        return _identifier_only(get_args(annotation)[0], name)
    if origin in (Union, types.UnionType, list, tuple, frozenset, set):
        return all(_identifier_only(a, name) for a in get_args(annotation) if a is not Ellipsis)
    if annotation is str:
        return bool(_ID_NAME.match(name))
    if isinstance(annotation, type):
        if issubclass(annotation, enum.Enum) or issubclass(annotation, _SCALARS):
            return True
        if issubclass(annotation, BaseModel):
            return all(
                _identifier_only(f.annotation, n) for n, f in annotation.model_fields.items()
            )
    return False


def row_fields(model: type[BaseModel]) -> dict[str, type[BaseModel]]:
    """An output model's row lists: each list field whose items are models."""
    rows: dict[str, type[BaseModel]] = {}
    for name, field in model.model_fields.items():
        annotation = field.annotation
        if get_origin(annotation) in (list, tuple):
            args = [a for a in get_args(annotation) if a is not Ellipsis]
            if len(args) == 1 and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                rows[name] = args[0]
    return rows


_TOOLS: dict[str, AgentTool] = {}
# The input fields the runtime resolves targets from (`runtime.default_targets`).
_TARGET_FIELDS: Final = frozenset(
    {"engagement_id", "engagement_ids", "client_id", "client_entity_id", "client_entity_ids"}
)


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
    _validate_shapes(tool)


def _validate_shapes(tool: AgentTool) -> None:
    """P-10-T22: the shapes the runtime relies on (module docstring)."""
    out = tool.output_model
    if tool.max_rows < 1:
        raise ToolInvalid(f"tool {tool.name!r}: max_rows is at least 1")
    missing = [f for f in tool.untrusted if f not in out.model_fields]
    if missing:
        raise ToolInvalid(f"tool {tool.name!r}: untrusted names no output field {missing}")
    # S32 review: the runtime authorises the records an input names by the conventional fields;
    # a write naming records any other way declares its own targets (`tool_targets`), or its
    # effect would be checked against the run's engagement only. A read's shape stays as C6 v2
    # froze it (`tax.read_return_summary` takes `return_id`); its handler scopes the record to
    # the run's engagement, and T-04-T08 declares targets when it builds the tool.
    named = [
        n
        for n in tool.input_model.model_fields
        if (n.endswith("_id") or n.endswith("_ids")) and n not in _TARGET_FIELDS
    ]
    writes = tool.kind in ("propose", "approved_write")
    if writes and named and not callable(getattr(tool.input_model, "tool_targets", None)):
        raise ToolInvalid(f"tool {tool.name!r}: {named} name records; declare tool_targets")
    if tool.paginate and not (
        issubclass(tool.input_model, ToolPageIn) and issubclass(out, ToolPageOut)
    ):
        raise ToolInvalid(
            f"tool {tool.name!r}: a paginated tool takes ToolPageIn, answers ToolPageOut"
        )
    if tool.kind == "read":
        for name, row in row_fields(out).items():
            if "id" not in row.model_fields:
                raise ToolInvalid(f"tool {tool.name!r}: rows in {name!r} carry an id (ADR-049)")
    if tool.kind in ("propose", "approved_write"):
        if tool.untrusted:
            raise ToolInvalid(f"tool {tool.name!r}: a write answers no client content")
        texty = [n for n, f in out.model_fields.items() if not _identifier_only(f.annotation, n)]
        if texty:
            raise ToolInvalid(
                f"tool {tool.name!r}: a {tool.kind} tool answers identifiers only, not {texty}"
            )


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
