"""Registration slots for client-access scopes and consents (F-03-T08; chapter 03 §2.4).

Owners register how to resolve a scope (engagements: work_item, intake; requests: request_item;
tax: k1_package; assurance: governance_room, component) and how to check a consent
(organisations). Both fail closed: an unresolved scope is denied, an unregistered consent is not
given.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from abacus.kernel.db import TenantContext

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

    from abacus.kernel.uow import AuditRow, UnitOfWork
    from abacus.modules.identity.authz import Resource


@dataclass(frozen=True)
class ScopeFacts:
    client_id: UUID
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None


ScopeResolver = Callable[[TenantContext, UUID], Awaitable[ScopeFacts | None]]
ConsentCheck = Callable[[TenantContext, UUID, str, datetime], Awaitable[bool]]
_SCOPES: dict[str, ScopeResolver] = {}
_CONSENTS: dict[str, ConsentCheck] = {}


def _same(a: Callable[..., object], b: Callable[..., object]) -> bool:
    """The same function, even from a module executed twice (a reloaded `api.py`)."""
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def register_scope_resolver(scope_kind: str, lookup: ScopeResolver) -> None:
    known = _SCOPES.get(scope_kind)
    if known is not None and not _same(known, lookup):
        raise ValueError(f"scope kind {scope_kind!r} is already registered")
    _SCOPES[scope_kind] = lookup


async def resolve_scope(
    tenant: TenantContext, scope_kind: str, scope_id: UUID
) -> ScopeFacts | None:
    """The scope's facts, or None (deny) when the kind is unregistered or the scope unknown."""
    lookup = _SCOPES.get(scope_kind)
    return None if lookup is None else await lookup(tenant, scope_id)


# G-01-T09 (DEC-52, AC9.2): the same consent as a SQL predicate over a client-id column, for
# `visible()`'s offshore filter. Registered with the check; without one, no client qualifies.
ConsentColumn = Callable[[Any, str], "ColumnElement[bool]"]  # Any: the client-id column
# How many of the firm's clients the consent covers now (ADM-03d's "clients with a valid
# offshore consent"); unregistered, 0.
ConsentCount = Callable[[TenantContext, str], Awaitable[int]]
_CONSENT_COLUMNS: dict[str, ConsentColumn] = {}
_CONSENT_COUNTS: dict[str, ConsentCount] = {}
OFFSHORE_DISCLOSURE = "offshore_disclosure"


def register_consent_check(
    purpose: str,
    lookup: ConsentCheck,
    column: ConsentColumn | None = None,
    count: ConsentCount | None = None,
) -> None:
    """`column` turns a client-id column into "a valid consent for `purpose` covers it" (T-01
    registers both for `offshore_disclosure`; C19)."""
    if purpose in _CONSENTS:
        raise ValueError(f"consent purpose {purpose!r} is already registered")
    _CONSENTS[purpose] = lookup
    if column is not None:
        _CONSENT_COLUMNS[purpose] = column
    if count is not None:
        _CONSENT_COUNTS[purpose] = count


async def consented_count(tenant: TenantContext, purpose: str) -> int:
    counter = _CONSENT_COUNTS.get(purpose)
    return 0 if counter is None else await counter(tenant, purpose)


def consent_column(purpose: str) -> ConsentColumn | None:
    """The registered predicate builder, or None (callers admit nothing: fail closed)."""
    return _CONSENT_COLUMNS.get(purpose)


async def consent_given(
    tenant: TenantContext, entity_id: UUID, purpose: str, at: datetime
) -> bool:
    """Whether a consent covers the purpose; an unregistered purpose is never given."""
    lookup = _CONSENTS.get(purpose)
    return False if lookup is None else await lookup(tenant, entity_id, purpose, at)


# --- F-03-T30: an engagement as an authorisation resource, built from its row by engagements ---

EngagementResource = Callable[[TenantContext, UUID], Awaitable["Resource"]]
_ENGAGEMENT_RESOURCE: list[EngagementResource] = []


def register_engagement_resource(lookup: EngagementResource) -> None:
    """engagements: (tenant, engagement id) -> its `Resource` (archived from the row), or
    `NotFound`. For modules that may not import engagements (platform's capabilities)."""
    if _ENGAGEMENT_RESOURCE and not _same(_ENGAGEMENT_RESOURCE[0], lookup):
        raise ValueError("the engagement resource lookup is already registered")
    _ENGAGEMENT_RESOURCE[:] = [lookup]


async def engagement_resource(tenant: TenantContext, engagement_id: UUID) -> Resource:
    """The engagement's `Resource`; `NotFound` when unknown or nothing is registered."""
    from abacus.kernel.errors import NotFound

    if not _ENGAGEMENT_RESOURCE:
        raise NotFound("engagement")
    return await _ENGAGEMENT_RESOURCE[0](tenant, engagement_id)


# P-01-T04: organisations owns `offices`; identity reads a firm's offices through this slot for
# `/v1/me` (the office list and the default office filter). Unregistered: no offices.
OfficeList = Callable[[TenantContext], Awaitable[list[tuple[UUID, str]]]]
_OFFICES: list[OfficeList] = []


def register_office_list(lookup: OfficeList) -> None:
    if _OFFICES and not _same(_OFFICES[0], lookup):
        raise ValueError("the office list is already registered")
    _OFFICES[:] = [lookup]


async def firm_offices(tenant: TenantContext) -> list[tuple[UUID, str]]:
    """The firm's offices, (id, name) by name; empty when nothing is registered."""
    return await _OFFICES[0](tenant) if _OFFICES else []


# --- invitations v2 (P-08-T18): who an invitation is for, and the contact it activates ---------


@dataclass(frozen=True)
class InvitationParties:
    """POR-01 d's names: the invitee contact's name and organisation, and what the access covers
    (the engagement's client entity, e.g. "Northwind Robotics 401(k) Plan")."""

    scope_label: str
    invitee_name: str | None = None
    organisation_name: str | None = None


InvitationPartiesLookup = Callable[
    [TenantContext, UUID, UUID | None], Awaitable[InvitationParties | None]
]
# The caller's unit of work, the contact and the person who accepted for it.
ContactActivation = Callable[["UnitOfWork", UUID, UUID], Awaitable[None]]
_PARTIES: list[InvitationPartiesLookup] = []
_ACTIVATION: list[ContactActivation] = []


def register_invitation_parties(lookup: InvitationPartiesLookup) -> None:
    if _PARTIES and not _same(_PARTIES[0], lookup):
        raise ValueError("the invitation parties are already registered")
    _PARTIES[:] = [lookup]


async def invitation_parties(
    tenant: TenantContext, engagement_id: UUID, contact_id: UUID | None
) -> InvitationParties | None:
    """None when nothing is registered or the engagement is unknown (the preview answers 404)."""
    return await _PARTIES[0](tenant, engagement_id, contact_id) if _PARTIES else None


def register_contact_activation(activate: ContactActivation) -> None:
    if _ACTIVATION and not _same(_ACTIVATION[0], activate):
        raise ValueError("the contact activation is already registered")
    _ACTIVATION[:] = [activate]


async def activate_contact(tx: UnitOfWork, contact_id: UUID, user_id: UUID) -> None:
    """The invitation's contact becomes active for the person, in the acceptance's unit of work.
    Unregistered, the acceptance fails (the contact would stay "invited" forever)."""
    if not _ACTIVATION:
        raise LookupError("no contact activation is registered")
    await _ACTIVATION[0](tx, contact_id, user_id)


# G-01-T05: organisations owns `team_rosters`; identity reads a person's teams for ADM-02 and
# writes them when an admin edits the person (or an invitation is accepted). Unregistered: no
# teams, and a write naming teams is refused. G-01-T08 (AC7.4): `lines` answers, in the caller's
# unit of work, which service lines the firm's service-line teams manage and which of them the
# person's teams hold, so identity keeps `memberships.service_lines` in agreement.
MemberTeams = Callable[[TenantContext, list[UUID]], Awaitable[dict[UUID, list[UUID]]]]
SetMemberTeams = Callable[["UnitOfWork", UUID, UUID, list[UUID]], Awaitable[bool]]
ServiceLineTeams = Callable[["UnitOfWork", UUID], Awaitable[tuple[frozenset[str], frozenset[str]]]]
_TEAMS: list[tuple[MemberTeams, SetMemberTeams, ServiceLineTeams | None]] = []


def register_member_teams(
    read: MemberTeams, write: SetMemberTeams, lines: ServiceLineTeams | None = None
) -> None:
    if _TEAMS and not (_same(_TEAMS[0][0], read) and _same(_TEAMS[0][1], write)):
        raise ValueError("member teams are already registered")
    _TEAMS[:] = [(read, write, lines)]


async def member_teams(tenant: TenantContext, user_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    """Each person's teams (empty when nothing is registered)."""
    return await _TEAMS[0][0](tenant, user_ids) if _TEAMS and user_ids else {}


async def set_member_teams(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, team_ids: list[UUID]
) -> bool:
    """Replace the person's teams; False when a team isn't the firm's (or none is registered)."""
    if not _TEAMS:
        return not team_ids
    return await _TEAMS[0][1](tx, tenant_id, user_id, team_ids)


async def service_line_teams(
    tx: UnitOfWork, user_id: UUID
) -> tuple[frozenset[str], frozenset[str]]:
    """(lines the firm's service-line teams manage, lines the person's teams hold); none when
    nothing is registered, so every line is then set directly."""
    if not _TEAMS or _TEAMS[0][2] is None:
        return frozenset(), frozenset()
    return await _TEAMS[0][2](tx, user_id)


# --- a contact's delegated requests (P-07-T25; C5): requests records, ends and counts them; the
# grants are identity's, the contact organisations'. Unregistered, a delegated invitation fails. --

# (tx, contact, [(grant, request item)], by) in the caller's unit of work.
DelegationRecord = Callable[
    ["UnitOfWork", UUID, Sequence[tuple[UUID, UUID]], UUID], Awaitable[None]
]
# (tx, grant ids) -> the request items whose delegation ended.
DelegationEnd = Callable[["UnitOfWork", Sequence[UUID]], Awaitable[list[UUID]]]
# (tenant, contacts) -> per contact, the requests delegated now and those of them received.
DelegationCounts = Callable[
    [TenantContext, Sequence[UUID]],
    Awaitable[dict[UUID, tuple[tuple[UUID, ...], tuple[UUID, ...]]]],
]


@dataclass(frozen=True)
class Delegations:
    record: DelegationRecord
    end: DelegationEnd
    counts: DelegationCounts


_DELEGATIONS: list[Delegations] = []


def register_contact_delegations(
    record: DelegationRecord, end: DelegationEnd, counts: DelegationCounts
) -> None:
    found = Delegations(record, end, counts)
    if _DELEGATIONS and not _same(_DELEGATIONS[0].record, record):
        raise ValueError("the contact delegations are already registered")
    _DELEGATIONS[:] = [found]


def contact_delegations_provider() -> Delegations:
    """The registered provider; unregistered fails (a delegation would go unrecorded)."""
    if not _DELEGATIONS:
        raise RuntimeError("no contact delegations provider is registered")
    return _DELEGATIONS[0]


# --- walls v2 (G-01-T09): what other modules tell identity about a wall's client and effects ----

# organisations: the client's relationship partner (AC8.3), or `None` for a client with none;
# `False` when the firm has no such client (the wall answers 404).
ClientPartner = Callable[[TenantContext, UUID], Awaitable[UUID | bool | None]]
_CLIENT_PARTNER: list[ClientPartner] = []


def register_client_partner(lookup: ClientPartner) -> None:
    if _CLIENT_PARTNER and not _same(_CLIENT_PARTNER[0], lookup):
        raise ValueError("the client partner lookup is already registered")
    _CLIENT_PARTNER[:] = [lookup]


async def client_partner(tenant: TenantContext, client_id: UUID) -> UUID | bool | None:
    """Unregistered: no client is known (a wall can't be previewed or created; fail closed)."""
    return await _CLIENT_PARTNER[0](tenant, client_id) if _CLIENT_PARTNER else False


# engagements: the person's current work-item assignments on the client's engagements, counted
# for the preview (AC8.1) and ended by the `wall.created` consumer (AC8.5) as the system on
# behalf of the wall's creator, one removal row and audit row each; returns how many ended.
WallAssignmentCount = Callable[[TenantContext, UUID, UUID], Awaitable[int]]
WallAssignmentEnd = Callable[["UnitOfWork", UUID, UUID, UUID, UUID], Awaitable[int]]
_WALL_ASSIGNMENTS: list[tuple[WallAssignmentCount, WallAssignmentEnd]] = []


def register_wall_assignments(count: WallAssignmentCount, end: WallAssignmentEnd) -> None:
    if _WALL_ASSIGNMENTS and not _same(_WALL_ASSIGNMENTS[0][0], count):
        raise ValueError("the wall assignments are already registered")
    _WALL_ASSIGNMENTS[:] = [(count, end)]


async def wall_assignment_count(tenant: TenantContext, user_id: UUID, client_id: UUID) -> int:
    return await _WALL_ASSIGNMENTS[0][0](tenant, user_id, client_id) if _WALL_ASSIGNMENTS else 0


async def end_wall_assignments(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, client_id: UUID, on_behalf_of: UUID
) -> int:
    if not _WALL_ASSIGNMENTS:
        return 0
    return await _WALL_ASSIGNMENTS[0][1](tx, tenant_id, user_id, client_id, on_behalf_of)


# audit_trail: one target's events, newest first (`events_for_target`), for the wall log
# (AC8.6). Unregistered, a wall's log is empty.
TargetEvents = Callable[[TenantContext, str, UUID, int | None, int], Awaitable[list["AuditRow"]]]
_TARGET_EVENTS: list[TargetEvents] = []


def register_target_events(reader: TargetEvents) -> None:
    if _TARGET_EVENTS and not _same(_TARGET_EVENTS[0], reader):
        raise ValueError("the target events reader is already registered")
    _TARGET_EVENTS[:] = [reader]


async def target_events(
    tenant: TenantContext, kind: str, target_id: UUID, before_seq: int | None, limit: int
) -> list[AuditRow]:
    if not _TARGET_EVENTS:
        return []
    return await _TARGET_EVENTS[0](tenant, kind, target_id, before_seq, limit)
