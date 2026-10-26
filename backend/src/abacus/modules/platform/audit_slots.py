"""The audit-log labeler and value-resolver slots (G-02-T02 declarations; SPEC-349 §8; DEC-60).

The audit log stores identifiers only (`kernel.uow.Ref`). ADM-07 shows names and, for a viewer
with the right to see them, before and after values, resolved at read time by the module that
owns each target type:

- a **labeler** turns target ids of one type into display labels ("Copperleaf Coffee Roasters,
  Inc."). A label declares its classification; anything above `confidential` is refused, so the
  label index (G-02-T10) never holds Restricted text.
- a **value resolver** answers one event's values section for one viewer: `resolved` rows
  (already masked by classification), `withheld` with a reason, or `unavailable`.

Both fail closed: an unregistered type has no label and its values are `unavailable` ("Values
not available"); a resolver that raises answers `unavailable` too. Modules register at import
through `platform.api`; the audit trail reads through `audit_label` and `audit_values` (G-02-T08,
T09). Nothing here writes, and nothing a resolver returns is ever stored.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from abacus.kernel.logging import get_logger
from abacus.modules.identity.api import AuthContext

LabelClass = Literal["public", "internal", "confidential", "restricted"]
ValuesStatus = Literal["resolved", "withheld", "unavailable"]
# Why values are withheld; the SPA words each reason (ADM-07c variant, DEC-415 Q1).
WithheldReason = Literal["need_to_know", "walled", "not_enabled"]
_LABELLABLE: Final = frozenset({"public", "internal", "confidential"})
_log = get_logger(__name__)


@dataclass(frozen=True)
class AuditLabel:
    text: str
    classification: LabelClass


@dataclass(frozen=True)
class AuditEventRef:
    """What a resolver may know about the event: identifiers and references, never values."""

    seq: int
    action: str
    target_type: str
    target_id: str
    before_ref: Mapping[str, str | int] | None
    after_ref: Mapping[str, str | int] | None


@dataclass(frozen=True)
class AuditValueRow:
    """One field's before and after, as the viewer may see them (masked where Restricted)."""

    field: str
    before: str | None
    after: str | None
    masked: bool = False


@dataclass(frozen=True)
class AuditValues:
    status: ValuesStatus
    reason: WithheldReason | None = None
    rows: tuple[AuditValueRow, ...] = ()
    # Facts about related items left out of the change ("Not included"), identifiers and codes.
    not_included: tuple[Mapping[str, str | int], ...] = field(default=())


UNAVAILABLE: Final = AuditValues("unavailable")

AuditLabeler = Callable[[AuthContext, Sequence[str]], Awaitable[Mapping[str, AuditLabel]]]
AuditValueResolver = Callable[[AuthContext, AuditEventRef], Awaitable[AuditValues]]
_LABELERS: dict[str, AuditLabeler] = {}
_RESOLVERS: dict[str, AuditValueResolver] = {}


def register_audit_labeler(target_type: str, labeler: AuditLabeler) -> None:
    if target_type in _LABELERS:
        raise ValueError(f"audit labeler {target_type!r} is already registered")
    _LABELERS[target_type] = labeler


def register_audit_value_resolver(target_type: str, resolver: AuditValueResolver) -> None:
    if target_type in _RESOLVERS:
        raise ValueError(f"audit value resolver {target_type!r} is already registered")
    _RESOLVERS[target_type] = resolver


async def audit_labels(
    viewer: AuthContext, target_type: str, target_ids: Sequence[str]
) -> dict[str, AuditLabel]:
    """Labels for the ids its owner can name; none for an unregistered type or a failure, and
    never a label classified above `confidential`."""
    labeler = _LABELERS.get(target_type)
    if labeler is None or not target_ids:
        return {}
    try:
        found = await labeler(viewer, target_ids)
    except Exception as exc:  # fail closed: the row keeps its identifier
        _log.warning("audit.labeler_failed", target_type=target_type, error=type(exc).__name__)
        return {}
    return {i: label for i, label in found.items() if label.classification in _LABELLABLE}


async def audit_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """The event's values section for `viewer`; `unavailable` when its type has no resolver or
    the resolver fails."""
    resolver = _RESOLVERS.get(event.target_type)
    if resolver is None:
        return UNAVAILABLE
    try:
        return await resolver(viewer, event)
    except Exception as exc:
        _log.warning(
            "audit.resolver_failed", target_type=event.target_type, error=type(exc).__name__
        )
        return UNAVAILABLE


def registered_audit_types() -> tuple[frozenset[str], frozenset[str]]:
    """The target types with a labeler and with a value resolver (the catalogue check, T08)."""
    return frozenset(_LABELERS), frozenset(_RESOLVERS)
