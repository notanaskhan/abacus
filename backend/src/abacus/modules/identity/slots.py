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
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext

if TYPE_CHECKING:
    from abacus.kernel.uow import UnitOfWork
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


def register_consent_check(purpose: str, lookup: ConsentCheck) -> None:
    if purpose in _CONSENTS:
        raise ValueError(f"consent purpose {purpose!r} is already registered")
    _CONSENTS[purpose] = lookup


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
# teams, and a write naming teams is refused.
MemberTeams = Callable[[TenantContext, list[UUID]], Awaitable[dict[UUID, list[UUID]]]]
SetMemberTeams = Callable[["UnitOfWork", UUID, UUID, list[UUID]], Awaitable[bool]]
_TEAMS: list[tuple[MemberTeams, SetMemberTeams]] = []


def register_member_teams(read: MemberTeams, write: SetMemberTeams) -> None:
    if _TEAMS and not (_same(_TEAMS[0][0], read) and _same(_TEAMS[0][1], write)):
        raise ValueError("member teams are already registered")
    _TEAMS[:] = [(read, write)]


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


# --- P-08-T21: a portal email's secure link at sign-in (communications owns the links) ---------

LinkOutcome = Literal["bad", "other", "claimed"]
LinkClaim = Callable[[str, str, str], Awaitable[LinkOutcome]]
_LINK_CLAIM: list[LinkClaim] = []


def register_link_claim(claim: LinkClaim) -> None:
    """communications: (host, link token, typed email) -> `bad` for every link that can't be
    used (unknown, another firm's, used, revoked, expired), `claimed` when the address is the
    link's (which uses it), `other` otherwise."""
    if _LINK_CLAIM and not _same(_LINK_CLAIM[0], claim):
        raise ValueError("the link claim is already registered")
    _LINK_CLAIM[:] = [claim]


async def claim_link(host: str, token: str, email: str) -> LinkOutcome:
    """Fails closed: with no claim registered every link is `bad`."""
    return "bad" if not _LINK_CLAIM else await _LINK_CLAIM[0](host, token, email)


# P-08-T21 (security review): a contact's secure links die with their access or their address.
ContactLinksRevoker = Callable[["UnitOfWork", Sequence[UUID]], Awaitable[int]]
_LINKS_REVOKER: list[ContactLinksRevoker] = []


def register_contact_links_revoker(revoker: ContactLinksRevoker) -> None:
    """communications: revoke every live secure link of these contacts in the caller's unit of
    work; how many."""
    if _LINKS_REVOKER and not _same(_LINKS_REVOKER[0], revoker):
        raise ValueError("the contact links revoker is already registered")
    _LINKS_REVOKER[:] = [revoker]


async def revoke_contact_links(tx: UnitOfWork, contact_ids: Sequence[UUID]) -> int:
    """Called where a contact's access ends or their address changes (organisations)."""
    if not _LINKS_REVOKER or not contact_ids:
        return 0
    return await _LINKS_REVOKER[0](tx, contact_ids)
