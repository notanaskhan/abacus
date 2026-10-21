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
