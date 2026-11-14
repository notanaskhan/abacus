"""Agent tool declarations, the ADR-106 slot between owning modules and C17 (P-10-T28; ADR-233;
`docs/contracts/tool-registry.md` §2). PROTECTED.

The modules that own the data (engagements, requests, evidence, methodology, ledger) cannot import
`agents`, which imports them (ADR-008), and `ledger` imports nothing at all. So each declares its
tools here as `ToolDecl` records in `<module>/agent_tools.py`, listed as its api's `AGENT_TOOLS`;
`agents.tools.catalogue` collects every module's list and registers them through
`register_tool`, which validates each (C17 rules: names, kinds, never-verbs, 200 rows, ids,
description prompts) at import.

A handler is `async def f(caller: ToolCaller, args: In) -> Out`. `caller` is the run's
`AgentContext`; a handler reads only what its arguments name, inside the engagements and clients
the runtime has already authorised (`client_scope`, `task_scope`, walls, the matrix), and scopes
every query to them. It never authorises, never writes, and computes every total in code
(ADR-050).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Final, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext

ToolKind = Literal["read", "compute", "propose", "approved_write"]
# W-02-T19 (DEC-4930): the per-item failure ledger. A read that reaches many items and cannot read
# some answers what it read and names the rest here, by reference and code, never content. A tool
# that supports re-reading only those items takes them back as `only_refs` (`ONLY_REFS`).
ONLY_REFS: Final = "only_refs"
MAX_FAILED_ITEMS: Final = 1000
_CODE: Final = r"^[a-z][a-z0-9_]*$"
_INT: Final = classified("internal")
DataClass = Literal["internal", "confidential", "restricted", "tri"]
MAX_ROWS: Final = 200


class ToolCaller(Protocol):
    """What a handler may know of its caller: the tenant and the run's engagement (None for a
    firm-level run). `AgentContext` satisfies it."""

    @property
    def tenant(self) -> TenantContext: ...

    @property
    def engagement_id(self) -> UUID | None: ...


class FailedItem(BaseModel):
    """One item a step could not read (W-02 §4.2 `failed_items[]`): identifiers and a code only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_type: Annotated[str, Field(min_length=1, max_length=40, pattern=_CODE), _INT]
    ref_id: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$"), _INT]
    source: Annotated[str, Field(min_length=1, max_length=40, pattern=_CODE), _INT]
    error_code: Annotated[str, Field(min_length=1, max_length=40, pattern=_CODE), _INT]


@dataclass(frozen=True)
class ToolDecl:
    """One tool as its owning module declares it (C17 §2); `agents` registers it."""

    name: str
    kind: ToolKind
    action: str
    data_class: DataClass
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[..., Awaitable[BaseModel]]
    untrusted: tuple[str, ...] = ()
    max_rows: int = MAX_ROWS
    paginate: bool = False
    records_read: str | None = None
    scope_action: str | None = None  # P-10-T38: an approved_write's task-scope reach (C17 §2)

    @property
    def description(self) -> str:
        return f"tool.{self.name}@v1"
