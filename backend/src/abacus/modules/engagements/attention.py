"""The attention providers (I-02-T11; I-02 F2 "Needs attention"; C1, C3; DEC-88; DEC-4723). Amber.

`register_attention_provider(kind, provider)` is a fail-closed slot (a second registration of a
kind with another function is refused): each provider answers the viewer's rows of its kind over
the engagements the viewer can open (`engagements_for`, `visible()`), metadata only. Asked for a
kind nobody registered, `attention_rows` skips it and logs it, never guesses.

First providers:
- `gates_blocking_requests` (engagements): an unmet G1 to G3 gate that blocks the engagement's
  requests (the Fairhaven letter, E11, unsigned: G3), one row per gate with its blocker codes.
- `outstanding_pbc` (requests, registered by that module): the engagement's PBC received of total
  while the report target has not been met ("Northwind PBC 11 of 24").

Work-item hooks (`register_work_item_hooks(kind, next_milestone=…, dependents=…)`): an owner
says what a work item waits on next and which other work items depend on it. Tax's 1065 names
the K-1 release as the next milestone and the recipients' returns as dependents (Ridgeline's
K-1s for the Feld and Shah 1040s). Under DEC-88's both-sides rule a dependent row is returned only
when the viewer can open both engagements (`dependents_visible`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from abacus.kernel.logging import get_logger
from abacus.modules.identity.api import AuthContext

_log = get_logger(__name__)


@dataclass(frozen=True)
class AttentionRow:
    kind: str
    engagement_id: UUID
    title: str
    detail: str
    work_item_id: UUID | None = None
    codes: tuple[str, ...] = ()
    counts: dict[str, int] = field(default_factory=dict[str, int])


AttentionProvider = Callable[[AuthContext, Sequence[UUID]], Awaitable[Sequence[AttentionRow]]]
_PROVIDERS: dict[str, AttentionProvider] = {}


def _same(a: object, b: object) -> bool:
    return (getattr(a, "__module__", None), getattr(a, "__qualname__", None)) == (
        getattr(b, "__module__", None),
        getattr(b, "__qualname__", None),
    )


def register_attention_provider(kind: str, provider: AttentionProvider) -> None:
    known = _PROVIDERS.get(kind)
    if known is not None and not _same(known, provider):
        raise ValueError(f"attention provider {kind!r} is already registered")
    _PROVIDERS[kind] = provider


async def attention_rows(
    ctx: AuthContext, kinds: Sequence[str] | None = None
) -> list[AttentionRow]:
    """The viewer's rows of each kind (all registered when `kinds` is None)."""
    from abacus.modules.engagements.service import engagements_for

    visible = [e.id for e in await engagements_for(ctx)]
    out: list[AttentionRow] = []
    for kind in kinds if kinds is not None else sorted(_PROVIDERS):
        provider = _PROVIDERS.get(kind)
        if provider is None:
            _log.warning("attention_kind_unregistered", kind=kind)  # skipped, never guessed
            continue
        out.extend(await provider(ctx, visible))
    return out


# --- the work-item hooks ------------------------------------------------------------------------

Milestone = Callable[[AuthContext, UUID], Awaitable[str | None]]
Dependents = Callable[[AuthContext, UUID], Awaitable[Sequence[tuple[UUID, UUID]]]]  # (wi, eng)


@dataclass(frozen=True)
class WorkItemHooks:
    next_milestone: Milestone | None = None
    dependents: Dependents | None = None


_HOOKS: dict[str, WorkItemHooks] = {}


def register_work_item_hooks(kind: str, hooks: WorkItemHooks) -> None:
    known = _HOOKS.get(kind)
    if known is not None and known != hooks:
        raise ValueError(f"work item hooks {kind!r} are already registered")
    _HOOKS[kind] = hooks


async def next_milestone(ctx: AuthContext, kind: str, work_item_id: UUID) -> str | None:
    hooks = _HOOKS.get(kind)
    if hooks is None or hooks.next_milestone is None:
        return None
    return await hooks.next_milestone(ctx, work_item_id)


async def dependents_visible(
    ctx: AuthContext, kind: str, work_item_id: UUID, own_engagement: UUID
) -> list[UUID]:
    """The dependents the viewer may see: both engagements open to them (DEC-88)."""
    from abacus.modules.engagements.service import engagements_for

    hooks = _HOOKS.get(kind)
    if hooks is None or hooks.dependents is None:
        return []
    visible = {e.id for e in await engagements_for(ctx)}
    if own_engagement not in visible:
        return []
    return [wi for wi, eng in await hooks.dependents(ctx, work_item_id) if eng in visible]


# --- the engagements module's own provider ------------------------------------------------------

C1: Final = ("G1", "G2", "G3")


async def gates_blocking_requests(
    ctx: AuthContext, engagements: Sequence[UUID]
) -> list[AttentionRow]:
    """An unmet G1 to G3 gate blocks the engagement's requests (C1)."""
    from abacus.modules.engagements.gates import engagement_gates
    from abacus.modules.engagements.service import engagements_for

    out: list[AttentionRow] = []
    by_id = {e.id: e for e in await engagements_for(ctx) if e.id in set(engagements)}
    for e in by_id.values():
        for gate in await engagement_gates(ctx.tenant, e.id, e.type):
            if gate.gate in C1 and not gate.met:
                out.append(
                    AttentionRow(
                        kind="gates_blocking_requests",
                        engagement_id=e.id,
                        title=f"{e.client_entity_name} · {gate.gate} not met",
                        detail="Requests wait until the gate is met",
                        codes=tuple(gate.blockers),
                    )
                )
    return out


def register() -> None:
    register_attention_provider("gates_blocking_requests", gates_blocking_requests)


__all__ = [
    "AttentionRow",
    "WorkItemHooks",
    "attention_rows",
    "dependents_visible",
    "gates_blocking_requests",
    "next_milestone",
    "register",
    "register_attention_provider",
    "register_work_item_hooks",
]
