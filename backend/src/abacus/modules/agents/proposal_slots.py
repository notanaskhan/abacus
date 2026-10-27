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
from collections.abc import Awaitable, Callable, Mapping
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


# P-04-T24 security review M4: which engagement a target belongs to, from its owner. A target
# whose owner states none can't receive a suggestion (fail closed).
TargetEngagement = Callable[[TenantContext, UUID], Awaitable[UUID | None]]
_ENGAGEMENT_OF: dict[str, TargetEngagement] = {}


def register_suggestion_target(
    target_type: str, *, engagement_of: TargetEngagement | None = None
) -> None:
    if not _CODE.fullmatch(target_type):
        raise ValueError(f"suggestion target {target_type!r} must be snake_case")
    _TARGETS.add(target_type)
    if engagement_of is not None:
        _ENGAGEMENT_OF[target_type] = engagement_of


def check_suggestion_target(target_type: str) -> None:
    if target_type not in _TARGETS:
        raise UnregisteredTarget


async def target_on_engagement(
    tenant: TenantContext, target_type: str, target_id: UUID, engagement_id: UUID
) -> bool:
    """Whether the target's owner says `target_id` belongs to `engagement_id`; False when the
    target type is unregistered, its owner states no engagement lookup, or the owner raises."""
    owner = _ENGAGEMENT_OF.get(target_type)
    if target_type not in _TARGETS or owner is None:
        return False
    try:
        return await owner(tenant, target_id) == engagement_id
    except Exception:
        return False


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


def register_suggestion_applier(
    target_type: str, applier: SuggestionApplier, *, engagement_of: TargetEngagement
) -> None:
    """The target's owner: adopting a suggestion on `target_type` (alone or in an approved
    change set) calls `applier`; `engagement_of` says which engagement a target belongs to.
    Registering also accepts the target for suggestions."""
    if not _CODE.fullmatch(target_type):
        raise ValueError(f"suggestion target {target_type!r} must be snake_case")
    known = _APPLIERS.get(target_type)
    if known is not None and not _same(known, applier):
        raise ValueError(f"suggestion applier {target_type!r} is already registered")
    _APPLIERS[target_type] = applier
    _TARGETS.add(target_type)
    _ENGAGEMENT_OF[target_type] = engagement_of


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


# --- P-04-T24 security review H, M2: the firm's threshold policy, computed on the server -------


@dataclass(frozen=True)
class ProposedValue:
    """One value a threshold policy weighs (before and after, typed `{t, v}`)."""

    target_type: str
    target_id: UUID
    field_key: str
    before: Mapping[str, object] | None
    after: Mapping[str, object] | None


@dataclass(frozen=True)
class ThresholdEvaluation:
    """What the firm's threshold policy says about a change set, computed by code (ADR-050).
    `review_required` names the approver the policy routes it to (P-08 dormant: a person)."""

    policy_id: UUID
    policy_name: str
    version: int
    result: Literal["within_threshold", "review_required"]
    approver_user_id: UUID | None = None


ThresholdEvaluate = Callable[
    [TenantContext, UUID, str, tuple[ProposedValue, ...]], Awaitable[ThresholdEvaluation | None]
]
# (tenant, engagement, person, evaluation): whether the person's own limit covers it.
ThresholdCovers = Callable[[TenantContext, UUID, UUID, ThresholdEvaluation], Awaitable[bool]]


@dataclass(frozen=True)
class ThresholdPolicy:
    """A proposal kind's threshold policy (K-02 and A-06 register theirs as firm content): the
    evaluation of a change set, and whether a person's approval limit covers an evaluation."""

    kind: str
    evaluate: ThresholdEvaluate
    covers: ThresholdCovers


_POLICIES: dict[str, ThresholdPolicy] = {}


def register_threshold_policy(policy: ThresholdPolicy) -> None:
    if not _CODE.fullmatch(policy.kind):
        raise ValueError(f"proposal kind {policy.kind!r} must be snake_case")
    known = _POLICIES.get(policy.kind)
    if known is not None and not (
        _same(known.evaluate, policy.evaluate) and _same(known.covers, policy.covers)
    ):
        raise ValueError(f"threshold policy {policy.kind!r} is already registered")
    _POLICIES[policy.kind] = policy


def threshold_policy(kind: str) -> ThresholdPolicy | None:
    """None: no threshold applies to the kind (no firm has thresholds before K-02)."""
    return _POLICIES.get(kind)
