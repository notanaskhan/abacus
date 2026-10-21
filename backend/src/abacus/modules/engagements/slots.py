"""Registration slots for work-item kinds and gates (F-03-T08; ADR-106 pattern; chapter 03 §2.4).

Service lines register their work-item kind (assurance, tax, closes, notices) and the gates they
compute (signatures G3, assurance G4 to G9). Engagements never imports them. A missing
registration fails closed: an unregistered kind can't be created, an unregistered gate is unmet.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final, Protocol
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict


class UnknownWorkItemKind(DomainConflict):
    code = "unknown_work_item_kind"


class WorkItemProvider(Protocol):
    """What a work-item kind's owner answers about one of its work items."""

    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str: ...


@dataclass(frozen=True)
class GateFact:
    met: bool
    blockers: tuple[str, ...] = field(default=())


GateProvider = Callable[[TenantContext, UUID], Awaitable[GateFact]]
GATES: Final = tuple(f"G{n}" for n in range(1, 10))
_KINDS: dict[str, WorkItemProvider] = {}
_GATES: dict[str, GateProvider] = {}


def register_work_item_kind(kind: str, provider: WorkItemProvider) -> None:
    if kind in _KINDS:
        raise ValueError(f"work-item kind {kind!r} is already registered")
    _KINDS[kind] = provider


def work_item_provider(kind: str) -> WorkItemProvider:
    """The kind's provider; an unregistered kind is refused (409 unknown_work_item_kind)."""
    try:
        return _KINDS[kind]
    except KeyError:
        raise UnknownWorkItemKind(kind) from None


def _same(a: Callable[..., object], b: Callable[..., object]) -> bool:
    """The same provider, also after its module is reloaded (a new function object)."""
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def register_gate_provider(gate: str, provider: GateProvider) -> None:
    if gate not in GATES:
        raise ValueError(f"gate {gate!r} is unknown")
    if gate in _GATES and not _same(_GATES[gate], provider):
        raise ValueError(f"gate {gate!r} is already registered")
    _GATES[gate] = provider


async def gate_fact(tenant: TenantContext, engagement_id: UUID, gate: str) -> GateFact:
    """Whether the engagement meets the gate; an unregistered gate is unmet."""
    provider = _GATES.get(gate)
    if provider is None:
        return GateFact(met=False, blockers=("no_gate_provider",))
    return await provider(tenant, engagement_id)


# --- Judgments for the EQR digest (SPEC-314; TASK-332) ----------------------------------------


@dataclass(frozen=True)
class Judgment:
    """A significant judgment as its owner states it, by code: a kind, a title and facts
    (label, value) the owner computed. The EQR digest is built from these; never model text."""

    kind: str
    title: str
    facts: tuple[tuple[str, str], ...]
    decided: bool


JudgmentSource = Callable[[TenantContext, UUID], Awaitable[list[Judgment]]]
_JUDGMENTS: dict[str, JudgmentSource] = {}


def register_judgment_source(name: str, source: JudgmentSource) -> None:
    known = _JUDGMENTS.get(name)
    if known is not None and not _same(known, source):
        raise ValueError(f"judgment source {name!r} is already registered")
    _JUDGMENTS[name] = source


async def judgments_of(tenant: TenantContext, engagement_id: UUID) -> list[Judgment]:
    """Every registered source's judgments, by source name (callers authorised first)."""
    out: list[Judgment] = []
    for name in sorted(_JUDGMENTS):
        out.extend(await _JUDGMENTS[name](tenant, engagement_id))
    return out
