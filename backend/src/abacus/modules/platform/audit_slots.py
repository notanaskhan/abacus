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

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.tin_patterns import has_tin
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
    # G-02-T08: the event's scope and attribution, identifiers only.
    engagement_id: UUID | None = None
    actor_kind: str | None = None
    actor_id: str | None = None
    trace_id: str | None = None


@dataclass(frozen=True)
class AuditValueRow:
    """One field's before and after, as the viewer may see them (masked where Restricted).

    `classification` is the field's (ADR-031): `audit_values` masks a Restricted row the resolver
    left unmasked, so a Restricted value never leaves the slot in clear (G-02-T09; AC-11).
    `amount` is a decimal string with two places, never a float."""

    field: str
    before: str | None
    after: str | None
    masked: bool = False
    item_label: str = ""
    amount: str | None = None
    classification: LabelClass = "confidential"


@dataclass(frozen=True)
class AuditNotIncluded:
    """An item left out of the change ("Not included"), classified like a value row (L8): a
    Restricted label leaves the slot masked and without its amount."""

    item_label: str
    reason_code: str
    amount: str | None = None
    routed_to_user_id: UUID | None = None
    classification: LabelClass = "confidential"


@dataclass(frozen=True)
class AuditValues:
    status: ValuesStatus
    reason: WithheldReason | None = None
    rows: tuple[AuditValueRow, ...] = ()
    not_included: tuple[AuditNotIncluded, ...] = field(default=())


UNAVAILABLE: Final = AuditValues("unavailable")
_AMOUNT: Final = re.compile(r"-?\d+\.\d{2}")
_MASK: Final = "\u2022"


def mask_value(value: str | None) -> str | None:
    """A Restricted value as ADM-07 shows it: every character but separators and the last four
    digits hidden (`900-00-2208` -> `•••-••-2208`); a value with fewer than five digits is hidden
    whole."""
    if value is None:
        return None
    digits = sum(ch.isdigit() for ch in value)
    keep = 4 if digits > 4 else 0
    out: list[str] = []
    for ch in reversed(value):
        if ch.isdigit() and keep:
            out.append(ch)
            keep -= 1
        elif ch in "-/ .":
            out.append(ch)
        else:
            out.append(_MASK)
    return "".join(reversed(out))


def _safe_row(row: AuditValueRow) -> AuditValueRow:
    """Mask a Restricted row the resolver left in clear; drop an amount that is not a decimal
    string. A Restricted row never carries an amount in clear either."""
    amount = row.amount if row.amount is not None and _AMOUNT.fullmatch(row.amount) else None
    if row.classification == "restricted" and not row.masked:
        return replace(
            row,
            before=mask_value(row.before),
            after=mask_value(row.after),
            amount=None,
            masked=True,
        )
    if row.classification == "restricted":
        amount = None
    return replace(row, amount=amount)


def _safe_not_included(item: AuditNotIncluded) -> AuditNotIncluded:
    amount = item.amount if item.amount is not None and _AMOUNT.fullmatch(item.amount) else None
    if item.classification == "restricted":
        return replace(item, item_label=mask_value(item.item_label) or "", amount=None)
    return replace(item, amount=amount)


def _safe(values: AuditValues) -> AuditValues:
    if values.status != "resolved":
        return AuditValues(values.status, values.reason)
    return replace(
        values,
        rows=tuple(_safe_row(r) for r in values.rows),
        not_included=tuple(_safe_not_included(n) for n in values.not_included),
    )


# A labeler's viewer is None when the label index asks (G-02-T10): the label must then suit
# anyone who may see the event, since the index serves every reader's search.
AuditLabeler = Callable[[AuthContext | None, Sequence[str]], Awaitable[Mapping[str, AuditLabel]]]
AuditValueResolver = Callable[[AuthContext, AuditEventRef], Awaitable[AuditValues]]
# Q-03-T235 (DEC-3304): a labeler that reads its own tables needs the firm, and the label index
# has no viewer, so a tenant labeler is called with the tenant (the viewer's, or the indexer's).
# Its label must suit anyone who may see the event: the event's visibility is the reader's check.
AuditTenantLabeler = Callable[[TenantContext, Sequence[str]], Awaitable[Mapping[str, AuditLabel]]]

_LABELERS: dict[str, AuditLabeler] = {}
_TENANT_LABELERS: dict[str, AuditTenantLabeler] = {}
_RESOLVERS: dict[str, AuditValueResolver] = {}
# Q-03-T235: the noun a target type reads as where no labeler names it (ADM-07, AUD-29), so a row
# never shows a bare identifier. A module may name its own types; any other reads from its code.
_NOUNS: dict[str, str] = {
    "agent_run": "Agent run",
    "audit_report": "Auditor's report",
    "audit_report_version": "Report version",
    "eqr_review": "EQR review",
    "evidence_item": "Document",
    "evidence_version": "Document version",
    "governance_communication": "Governance communication",
    "representation_letter": "Representation letter",
    "review_note": "Review note",
    "work_item": "Work item",
}
_ACRONYMS: Final = frozenset({"eqr", "pbc", "fs", "tb", "sum", "ai", "kba", "mfa", "sso", "pii"})


def register_audit_labeler(target_type: str, labeler: AuditLabeler) -> None:
    if target_type in _LABELERS:
        raise ValueError(f"audit labeler {target_type!r} is already registered")
    _LABELERS[target_type] = labeler


def _same(a: object, b: object) -> bool:
    """The same function, re-imported (a module reloaded registers its own labeler again)."""
    return (getattr(a, "__module__", None), getattr(a, "__qualname__", None)) == (
        getattr(b, "__module__", None),
        getattr(b, "__qualname__", None),
    )


def register_audit_tenant_labeler(target_type: str, labeler: AuditTenantLabeler) -> None:
    found = _TENANT_LABELERS.get(target_type)
    if target_type in _LABELERS or (found is not None and not _same(found, labeler)):
        raise ValueError(f"audit labeler {target_type!r} is already registered")
    _TENANT_LABELERS[target_type] = labeler


def register_audit_noun(target_type: str, noun: str) -> None:
    """A module's own word for one of its target types (sentence case, no identifier)."""
    if not noun.strip() or any(ch.isdigit() for ch in noun):
        raise ValueError(f"audit noun {noun!r} for {target_type!r}")
    _NOUNS[target_type] = noun.strip()


def audit_noun(target_type: str) -> str:
    """The catalogue noun for `target_type`: the module's, else its code in words
    (`legal_hold` -> "Legal hold", `eqr_checklist` -> "EQR checklist")."""
    found = _NOUNS.get(target_type)
    if found is not None:
        return found
    words = [w for w in target_type.split("_") if w]
    if not words:
        return "Record"
    shaped = [w.upper() if w in _ACRONYMS else w for w in words]
    first = shaped[0]
    shaped[0] = first if first.isupper() else first.capitalize()
    return " ".join(shaped)


def register_audit_value_resolver(target_type: str, resolver: AuditValueResolver) -> None:
    if target_type in _RESOLVERS:
        raise ValueError(f"audit value resolver {target_type!r} is already registered")
    _RESOLVERS[target_type] = resolver


async def audit_labels(
    viewer: AuthContext | None,
    target_type: str,
    target_ids: Sequence[str],
    *,
    tenant: TenantContext | None = None,
) -> dict[str, AuditLabel]:
    """Labels for the ids its owner can name; none for an unregistered type or a failure, and
    never a label classified above `confidential`. A tenant labeler reads as the viewer's firm,
    or as `tenant` where there is no viewer (the label index); with neither it names nothing."""
    if not target_ids:
        return {}
    labeler = _LABELERS.get(target_type)
    firm = viewer.tenant if viewer is not None else tenant
    by_tenant = _TENANT_LABELERS.get(target_type)
    try:
        if labeler is not None:
            found = await labeler(viewer, target_ids)
        elif by_tenant is not None and firm is not None:
            found = await by_tenant(firm, target_ids)
        else:
            return {}
    except Exception as exc:  # fail closed: the row keeps its identifier
        _log.warning("audit.labeler_failed", target_type=target_type, error=type(exc).__name__)
        return {}
    # Q-03-T235: a name is client content (ADR-052); one carrying a TIN form is Restricted text
    # whatever its labeler declared, so it is refused and the row reads as its noun.
    return {
        i: label
        for i, label in found.items()
        if label.classification in _LABELLABLE and not has_tin(label.text)
    }


async def audit_values(viewer: AuthContext, event: AuditEventRef) -> AuditValues:
    """The event's values section for `viewer`; `unavailable` when its type has no resolver or
    the resolver fails."""
    resolver = _RESOLVERS.get(event.target_type)
    if resolver is None:
        return UNAVAILABLE
    try:
        return _safe(await resolver(viewer, event))
    except Exception as exc:
        _log.warning(
            "audit.resolver_failed", target_type=event.target_type, error=type(exc).__name__
        )
        return UNAVAILABLE


@dataclass(frozen=True)
class AuditSource:
    """The run behind an event (ADM-07c Source): ids and times only; the SPA names the person."""

    run_id: UUID
    agent_id: str | None = None
    run_no: int | None = None
    started_at: datetime | None = None
    initiator_user_id: UUID | None = None


# (viewer, event) -> the run behind it, or None. Registered by the module that owns agent runs
# (agents, through `platform.api`); unregistered or failing, the drawer has no Source section.
AuditSourceResolver = Callable[[AuthContext, AuditEventRef], Awaitable[AuditSource | None]]
_SOURCE: list[AuditSourceResolver] = []


def register_audit_source(resolver: AuditSourceResolver) -> None:
    if _SOURCE and _SOURCE[0] is not resolver:
        raise ValueError("an audit source resolver is already registered")
    _SOURCE[:] = [resolver]


async def audit_source(viewer: AuthContext, event: AuditEventRef) -> AuditSource | None:
    """The run behind the event for `viewer`; None when nobody answers or the answer fails."""
    if not _SOURCE:
        return None
    try:
        return await _SOURCE[0](viewer, event)
    except Exception as exc:  # fail closed: no Source section
        _log.warning("audit.source_failed", error=type(exc).__name__)
        return None


def registered_audit_types() -> tuple[frozenset[str], frozenset[str]]:
    """The target types with a labeler and with a value resolver (the catalogue check, T08)."""
    return frozenset(_LABELERS) | frozenset(_TENANT_LABELERS), frozenset(_RESOLVERS)
