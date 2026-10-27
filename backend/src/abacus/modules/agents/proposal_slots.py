"""Where agent suggestions and proposals may land (P-04-T06; ADR-161).

- A module registers each target type its fields may receive suggestions on
  (`register_suggestion_target`).
- A module registers an adapter per proposal kind that applies an approved change set through
  its own service (`register_proposal_adapter`).
- P-04-T24: a target's owner registers the applier that writes an adopted or approved value in
  the approving unit of work (`register_suggestion_applier`); a kind other than
  `field_change_set` registers a change-set applier (`register_change_set_applier`).

Agents never write another module's rows. Fail closed: a suggestion on an unregistered target is
refused, and approving a proposal whose adapter isn't registered answers 503.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, ServiceUnavailable
from abacus.kernel.uow import UnitOfWork
from abacus.modules.identity.api import AuthContext

_CODE: Final = re.compile(r"[a-z][a-z_]{0,39}")
ProposalAdapter = Callable[[TenantContext, UUID], Awaitable[None]]
_TARGETS: set[str] = set()
_ADAPTERS: dict[str, ProposalAdapter] = {}


class UnregisteredTarget(DomainInvalid):
    """Nobody accepts suggestions on this target type."""

    code = "unregistered_target"


def register_suggestion_target(target_type: str) -> None:
    if not _CODE.fullmatch(target_type):
        raise ValueError(f"suggestion target {target_type!r} must be snake_case")
    _TARGETS.add(target_type)


def check_suggestion_target(target_type: str) -> None:
    if target_type not in _TARGETS:
        raise UnregisteredTarget


def register_proposal_adapter(kind: str, adapter: ProposalAdapter) -> None:
    if not _CODE.fullmatch(kind):
        raise ValueError(f"proposal kind {kind!r} must be snake_case")
    known = _ADAPTERS.get(kind)
    if known is not None and (known.__module__, known.__qualname__) != (
        adapter.__module__,
        adapter.__qualname__,
    ):
        raise ValueError(f"proposal kind {kind!r} is already registered")
    _ADAPTERS[kind] = adapter


async def apply_proposal(tenant: TenantContext, kind: str, proposal_id: UUID) -> None:
    adapter = _ADAPTERS.get(kind)
    if adapter is None:
        raise ServiceUnavailable
    await adapter(tenant, proposal_id)


# --- P-04-T24 (ADR-161 clause 1; DEC-602): where an approved value lands ------------------------


@dataclass(frozen=True)
class AdoptedValue:
    """One value a person approved or adopted, for its target's owner to write. `value` is typed
    (`{t, v}`); an edited value carries the person's citation note and `value_source = 'human'`
    (cause `edit`), an adopted one the agent's verified citations (`agent_suggested`, cause
    `suggestion_adopted`). `checkpoint_id` is the proposal's, so the field history links it."""

    engagement_id: UUID | None
    target_type: str
    target_id: UUID
    field_key: str
    value: dict[str, object]
    value_source: Literal["agent_suggested", "human"]
    cause: Literal["suggestion_adopted", "edit"]
    suggestion_id: UUID | None
    citation_ids: tuple[UUID, ...]
    citation_note: str | None
    checkpoint_id: UUID | None
    proposal_id: UUID | None


@dataclass(frozen=True)
class ApprovedChangeSet:
    """A proposal a person approved, for a kind's own applier (kinds other than
    `field_change_set`, whose rows go to each target's suggestion applier)."""

    proposal_id: UUID
    kind: str
    engagement_id: UUID | None
    decision: Literal["approved", "approved_with_edits"]
    values: tuple[AdoptedValue, ...]


# The owner writes in the approving unit of work, as the approving person: it authorises the
# write on its own target and records the value through `review.api.record_value`.
SuggestionApplier = Callable[[UnitOfWork, AuthContext, AdoptedValue], Awaitable[None]]
ChangeSetApplier = Callable[[UnitOfWork, AuthContext, ApprovedChangeSet], Awaitable[None]]
_APPLIERS: dict[str, SuggestionApplier] = {}
_CHANGE_SETS: dict[str, ChangeSetApplier] = {}


def _same(a: object, b: object) -> bool:
    return (getattr(a, "__module__", None), getattr(a, "__qualname__", None)) == (
        getattr(b, "__module__", None),
        getattr(b, "__qualname__", None),
    )


def register_suggestion_applier(target_type: str, applier: SuggestionApplier) -> None:
    """The target's owner: adopting a suggestion on `target_type` (alone or in an approved
    change set) calls `applier`. Registering also accepts the target for suggestions."""
    if not _CODE.fullmatch(target_type):
        raise ValueError(f"suggestion target {target_type!r} must be snake_case")
    known = _APPLIERS.get(target_type)
    if known is not None and not _same(known, applier):
        raise ValueError(f"suggestion applier {target_type!r} is already registered")
    _APPLIERS[target_type] = applier
    _TARGETS.add(target_type)


def suggestion_applier(target_type: str) -> SuggestionApplier:
    """Fail closed: no owner to write the value answers 503, before anything is written."""
    found = _APPLIERS.get(target_type)
    if found is None:
        raise ServiceUnavailable
    return found


def register_change_set_applier(kind: str, applier: ChangeSetApplier) -> None:
    if not _CODE.fullmatch(kind):
        raise ValueError(f"proposal kind {kind!r} must be snake_case")
    known = _CHANGE_SETS.get(kind)
    if known is not None and not _same(known, applier):
        raise ValueError(f"change set applier {kind!r} is already registered")
    _CHANGE_SETS[kind] = applier


def change_set_applier(kind: str) -> ChangeSetApplier:
    found = _CHANGE_SETS.get(kind)
    if found is None:
        raise ServiceUnavailable
    return found
