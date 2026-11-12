"""The workbench-sessions family, the rest of it (W-02-T02 stub; SPEC-653; W-02 §4.3; DEC-4604).
Contract: `docs/contracts/workbench-sessions.md`, additive to C6 v2.

The list and blank create are `sessions_contract.py`'s routes; this file holds rename, delete and
the context routes. Every route answers, in order: its matrix action (the router),
`workbench.enabled` (off: 404), then 501 until W-02-T09 (rename, delete) and W-02-T10 (context).

- Rename and delete are the session owner's (`session.manage`; anyone else 403, AC-L5). Delete is
  soft: items, runs and trace stay ("Its run trace stays in the firm audit log", AC-L4).
- Context options list only records the viewer can open (`visible()`, AC-C3): never a record they
  can't, and never a count of what was left out. A context item's summary lines are computed by
  code from the owning modules' APIs (AC-C4), never by a model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.workbench.sessions_contract import SessionSummaryOut, workbench_gate

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=40)]
Internal = classified("internal")
Confidential = classified("confidential")

ContextTab = Literal["client_record", "documents", "workpapers"]
# What a context item points at; the picker's tabs group them (WB-02 b).
ContextKind = Literal[
    "client",
    "client_entity",
    "engagement",
    "request_set",
    "document",
    "workpaper_set",
    "workpaper",
]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


class SessionRenameIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), Confidential]


class SessionDeletedOut(BaseModel):
    """The row leaves the list; its items, runs and trace stay (soft delete)."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    deleted_at: Annotated[datetime, Internal]


class ContextOptionOut(BaseModel):
    """A picker row (WB-02 b): a record the viewer can open, with its sub line."""

    model_config = _frozen()

    kind: Annotated[ContextKind, Internal]
    ref_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    detail: Annotated[str | None, Confidential] = None  # "Plan · PY2025 EBP Audit · Chicago"
    attached: Annotated[bool, Internal] = False  # already in the session's context


class ContextOptionsOut(BaseModel):
    model_config = _frozen()

    tab: Annotated[ContextTab, Internal]
    items: Annotated[list[ContextOptionOut], Confidential]
    # The footer copy is the screen's; no count of records left out exists (DEC-43).


class ContextRefIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[ContextKind, Internal]
    ref_id: Annotated[UUID, Internal]


class ContextAttachIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: Annotated[list[ContextRefIn], Field(min_length=1, max_length=12), Internal]


class ContextItemOut(BaseModel):
    """One attached item: the chip and the stack card (WB-02 c, d). `summary_lines` are computed
    by code (AC-C4): "24 requests · 12 received · 3 files in use"."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[ContextKind, Internal]
    ref_id: Annotated[UUID, Internal]
    card_title: Annotated[Literal["Client record", "Documents", "Workpapers"], Internal]
    chip_label: Annotated[str, Confidential]  # "PBC · 12 of 24"
    summary_lines: Annotated[list[str], Confidential]


class ContextItemsOut(BaseModel):
    """The session's context after the change; empty means firm-wide, read-only."""

    model_config = _frozen()

    session_id: Annotated[UUID, Internal]
    firm_wide: Annotated[bool, Internal]
    items: Annotated[list[ContextItemOut], Confidential]


def _not_yet() -> NoReturn:
    raise NotImplementedYet


manage_router = AbacusRouter(prefix="/v1/workbench/sessions", tags=["workbench sessions"])
context_options_router = AbacusRouter(
    prefix="/v1/workbench/context-options", tags=["workbench sessions"]
)


@manage_router.patch(
    "/{session_id}",
    action="session.manage",
    response_model=SessionSummaryOut,
    errors=(409, 501),
)
async def rename_session_route(
    session_id: UUID, body: SessionRenameIn, ctx: Ctx, if_match: IfMatch
) -> SessionSummaryOut:
    """The owner's rename; `title_source` becomes `manual`; 409 `stale_version` when `If-Match`
    is not the row's version; one `workbench_session.renamed` audit event (titles by hash)."""
    await workbench_gate(ctx)
    _not_yet()


@manage_router.delete(
    "/{session_id}", action="session.manage", response_model=SessionDeletedOut, errors=(501,)
)
async def delete_session_route(
    session_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SessionDeletedOut:
    """Soft delete; `workbench_session.deleted`; items, runs and trace are kept."""
    await workbench_gate(ctx)
    _not_yet()


@context_options_router.get(
    "", action="session.create", response_model=ContextOptionsOut, errors=(501,)
)
async def context_options_route(
    ctx: Ctx,
    tab: Annotated[ContextTab, Query()],
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    session_id: Annotated[UUID | None, Query()] = None,
) -> ContextOptionsOut:
    """Only records the viewer can open (AC-C3)."""
    await workbench_gate(ctx)
    _not_yet()


@manage_router.post(
    "/{session_id}/context",
    action="session.manage",
    response_model=ContextItemsOut,
    status_code=201,
    errors=(501,),
)
async def attach_context_route(
    session_id: UUID, body: ContextAttachIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ContextItemsOut:
    """One `context_added` item and audit event per record; a record the owner can't open is
    404 (no existence leak)."""
    await workbench_gate(ctx)
    _not_yet()


@manage_router.delete(
    "/{session_id}/context/{item_id}",
    action="session.manage",
    response_model=ContextItemsOut,
    errors=(501,),
)
async def remove_context_route(
    session_id: UUID, item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ContextItemsOut:
    """`context_removed`; later turns leave the record out of `client_scope` (AC-C5)."""
    await workbench_gate(ctx)
    _not_yet()
