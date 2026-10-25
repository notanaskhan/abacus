"""The contacts and portal-access contract, v1: CLI-04 (P-07-T17 stub; ADR-139, P-36, ADR-146).
Contract: `docs/contracts/contacts-access.md`; spec: SPEC-321 Story 5; DEC-226.

Behind `contacts.v2`: off, every route here answers 404. Live since P-07-T25 (`contacts.py`,
DEC-300): the contacts migration (0146), invitations re-scoped to contacts and pending grants,
delegated requests through C5, 14-day single-use links, resend, revoke, change scope, unlock, and
the firm's Invitation template through `communications`.

- A contact belongs to one client; its roles are per entity (`scope_kind` client or
  client_entity). Portal state is C2's `invitation` (Active · Invited · Not invited · Locked).
- An invitation carries grants: a grant role (ADR-146's codes), a scope (kind and id) and, for a
  delegate or third party, the request items it is limited to (C5 `delegate`). MFA comes from
  firm policy and the link expires in 14 days; neither is the caller's to choose beyond that.
- A full-client grant before any engagement of the client is Accepted is refused 409
  `gate_unmet` (G1); intake grants are the exception (P-07 OQ-11).
- Revoking keeps the requests with the client (never reassigned or deleted) and ends the
  contact's sessions (`access.changed`).
- The agent and the system are denied every write here at the matrix (INV-1); no client role
  holds any of these actions. A walled client answers 404 on every route (INV-3).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CONTACTS_V2, PORTAL_SIGN_IN_V2
from abacus.kernel._statuses import InvitationStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    ContactMfaResetOut,
    ContactPortalStatusOut,
    GrantRole,
    ScopeKind,
    current_context,
)
from abacus.modules.organisations import contacts as service

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

# P-07 §4.2 M3 (P-07-T25): `contact_roles.role` and `contacts.party_kind`.
ContactRole = Literal[
    "owner",
    "cfo",
    "controller",
    "trustee",
    "executor",
    "taxpayer",
    "spouse",
    "plan_sponsor_officer",
    "recordkeeper",
    "tpa",
    "custodian",
    "payroll_provider",
    "other",
]
PartyKind = Literal["person", "organisation", "group"]
RoleScopeKind = Literal["client", "client_entity"]
MfaPolicy = Literal["required_by_firm", "optional"]
# One address, `local@domain.tld`, on one line: no spaces, line breaks or a second `@` (DEC-303).
ContactEmail = Annotated[
    str, Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
ContactSort = Literal["name", "portal_status", "last_seen"]


class InvitationExpired(DomainConflict):
    """The invitation link is older than 14 days: ask the firm to resend it."""

    code = "invitation_expired"


class InvitationUsed(DomainConflict):
    """The invitation link was already used: it works once."""

    code = "invitation_used"


class ScopeOutsideClient(DomainInvalid):
    """A grant's scope, or a delegated request, is not the contact's client's."""

    code = "scope_outside_client"


# --- CLI-04 list --------------------------------------------------------------------------------


class ContactRoleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Annotated[ContactRole, classified("internal")]
    scope_kind: Annotated[RoleScopeKind, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]
    scope_name: Annotated[str, classified("confidential")]  # the entity's or client's name
    title_text: Annotated[str | None, classified("confidential")] = None


class ContactRowOut(BaseModel):
    """A CLI-04 row: roles per entity, portal state, MFA, last seen and delegated requests."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    party_kind: Annotated[PartyKind, classified("internal")]
    email: Annotated[str | None, classified("confidential")] = None
    roles: Annotated[list[ContactRoleOut], classified("confidential")] = []
    portal_status: Annotated[InvitationStatus, classified("internal")]  # C2 `invitation`
    invited_on: Annotated[date | None, classified("internal")] = None
    expires_on: Annotated[date | None, classified("internal")] = None
    mfa_enrolled: Annotated[bool | None, classified("internal")] = None
    last_seen_at: Annotated[datetime | None, classified("internal")] = None
    delegated_request_count: Annotated[int, classified("internal")] = 0
    allowed_actions: Annotated[list[str], classified("internal")] = []


class ContactCountsOut(BaseModel):
    """The header: "3 active · 1 invited · 2 not invited" (and locked when any)."""

    model_config = ConfigDict(frozen=True)

    active: Annotated[int, classified("internal")]
    invited: Annotated[int, classified("internal")]
    not_invited: Annotated[int, classified("internal")]
    locked: Annotated[int, classified("internal")]


class DelegatedFooterOut(BaseModel):
    """The footer: "10 + 9 + 2 + 2 + 1 = 24" and "PBC received 11 of 24". `parts` are the
    non-zero per-contact delegated counts in row order; `total` is their sum."""

    model_config = ConfigDict(frozen=True)

    parts: Annotated[list[int], classified("internal")]
    total: Annotated[int, classified("internal")]
    received: Annotated[int, classified("internal")]


class ContactsPage(ListPage[ContactRowOut]):
    """The P-36 envelope plus the header counts and the delegated-requests footer."""

    summary: Annotated[ContactCountsOut, classified("internal")]
    delegated: Annotated[DelegatedFooterOut, classified("internal")]


# --- O2 drawer ----------------------------------------------------------------------------------


class GrantOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    role: Annotated[GrantRole, classified("internal")]
    scope_kind: Annotated[ScopeKind, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]
    request_item_ids: Annotated[list[UUID], classified("internal")] = []
    status: Annotated[Literal["pending", "active", "revoked"], classified("internal")]
    granted_at: Annotated[datetime | None, classified("internal")] = None


class SignInEventOut(BaseModel):
    """A sign-in history line (P-08 events): what happened and when, never an address."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["signed_in", "code_failed", "locked", "unlocked"], classified("internal")
    ]
    at: Annotated[datetime, classified("internal")]


class ContactDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact: Annotated[ContactRowOut, classified("confidential")]
    grants: Annotated[list[GrantOut], classified("internal")] = []
    sign_ins: Annotated[list[SignInEventOut], classified("internal")] = []
    delegated_request_ids: Annotated[list[UUID], classified("internal")] = []
    version: Annotated[int, classified("internal")]


# --- writes -------------------------------------------------------------------------------------


class ContactRoleIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    role: Annotated[ContactRole, classified("internal")]
    scope_kind: Annotated[RoleScopeKind, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]
    title_text: Annotated[
        SingleLineText | None, Field(default=None, max_length=120), classified("confidential")
    ]


class ContactIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    name: Annotated[
        SingleLineText, Field(min_length=1, max_length=200), classified("confidential")
    ]
    party_kind: Annotated[PartyKind, classified("internal")] = "person"
    email: Annotated[ContactEmail | None, Field(default=None), classified("confidential")]
    phone: Annotated[
        SingleLineText | None, Field(default=None, max_length=40), classified("confidential")
    ]
    roles: Annotated[list[ContactRoleIn], Field(max_length=20), classified("confidential")] = []


class ContactPatchIn(BaseModel):
    """Absent fields are unchanged; `roles` replaces the list when present."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    name: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=200),
        classified("confidential"),
    ]
    email: Annotated[ContactEmail | None, Field(default=None), classified("confidential")]
    phone: Annotated[
        SingleLineText | None, Field(default=None, max_length=40), classified("confidential")
    ]
    roles: Annotated[
        list[ContactRoleIn] | None, Field(default=None, max_length=20), classified("confidential")
    ]


class ContactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact: Annotated[ContactRowOut, classified("confidential")]
    version: Annotated[int, classified("internal")]


class GrantIn(BaseModel):
    """One grant: a role on a scope; a delegate or third party names its request items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Annotated[GrantRole, classified("internal")]
    scope_kind: Annotated[ScopeKind, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]
    request_item_ids: Annotated[list[UUID], Field(max_length=200), classified("internal")] = []


class InvitationIn(BaseModel):
    """O3 "Invite…": MFA from firm policy, 14 days; the email is the firm's Invitation template."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grants: Annotated[list[GrantIn], Field(min_length=1, max_length=20), classified("internal")]
    expires_in_days: Annotated[Literal[14], classified("internal")] = 14


class InvitationOut(BaseModel):
    """CLI-04 c: "Invited · Sent Sep 14". Never the token: it goes only in the email."""

    model_config = ConfigDict(frozen=True)

    invitation_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    grants: Annotated[list[GrantOut], classified("internal")]
    mfa_policy: Annotated[MfaPolicy, classified("internal")]
    sent_at: Annotated[datetime, classified("internal")]
    expires_at: Annotated[datetime, classified("internal")]
    portal_status: Annotated[InvitationStatus, classified("internal")]  # `invited`


class InvitationRevokedOut(BaseModel):
    """Grants revoked, sessions ended; the delegated requests stay with the client."""

    model_config = ConfigDict(frozen=True)

    invitation_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    revoked_grant_ids: Annotated[list[UUID], classified("internal")]
    kept_request_item_ids: Annotated[list[UUID], classified("internal")] = []
    revoked_at: Annotated[datetime, classified("internal")]


class ContactAccessIn(BaseModel):
    """CLI-04 e "Change scope": the contact's whole grant set after the change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    grants: Annotated[list[GrantIn], Field(max_length=20), classified("internal")]


class ContactAccessOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID, classified("internal")]
    grants: Annotated[list[GrantOut], classified("internal")]
    version: Annotated[int, classified("internal")]


class ContactUnlockedOut(BaseModel):
    """CLI-04 d "Unlock…": the portal lock cleared; `contact.unlocked` audited."""

    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID, classified("internal")]
    portal_status: Annotated[InvitationStatus, classified("internal")]
    unlocked_at: Annotated[datetime, classified("internal")]


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, CONTACTS_V2):
        raise NotFound("contacts.v2")


def _row(view: service.RowView) -> ContactRowOut:
    return ContactRowOut.model_validate(asdict(view))


def _grants(views: list[service.GrantView]) -> list[GrantOut]:
    return [GrantOut.model_validate(asdict(v)) for v in views]


def _detail(view: service.DetailView) -> ContactDetailOut:
    return ContactDetailOut(
        contact=_row(view.contact),
        grants=_grants(view.grants),
        sign_ins=[],
        delegated_request_ids=view.delegated_request_ids,
        version=view.version,
    )


def _asked(grants: list[GrantIn]) -> list[service.GrantAsked]:
    return [
        service.GrantAsked(g.role, g.scope_kind, g.scope_id, tuple(g.request_item_ids))
        for g in grants
    ]


def _roles(roles: list[ContactRoleIn]) -> list[service.RoleAsked]:
    return [service.RoleAsked(r.role, r.scope_kind, r.scope_id, r.title_text) for r in roles]


def _invitation(view: service.InvitationView) -> InvitationOut:
    return InvitationOut(
        invitation_id=view.invitation_id,
        contact_id=view.contact_id,
        grants=_grants(view.grants),
        mfa_policy=view.mfa_policy,  # pyright: ignore[reportArgumentType] -- an MfaPolicy code
        sent_at=view.sent_at,
        expires_at=view.expires_at,
        portal_status=InvitationStatus(view.portal_status),
    )


client_contacts_router = AbacusRouter(prefix="/v1/clients", tags=["contacts"])
contacts_router = AbacusRouter(prefix="/v1/contacts", tags=["contacts"])
contact_invitations_router = AbacusRouter(prefix="/v1/invitations", tags=["contacts"])


@client_contacts_router.get(
    "/{client_id}/contacts", action="contact.read", response_model=ContactsPage
)
async def list_contacts_route(
    client_id: UUID,
    ctx: Ctx,
    portal_status: Annotated[InvitationStatus | None, Query()] = None,
    sort: Annotated[ContactSort, Query()] = "name",
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ContactsPage:
    """CLI-04 a: `counts` per portal status (the header) and the delegated footer."""
    await _gate(ctx)
    page = await service.list_contacts(
        ctx,
        client_id,
        portal_status=portal_status.value if portal_status is not None else None,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    return ContactsPage(
        items=[_row(r) for r in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        counts=page.counts,
        summary=ContactCountsOut.model_validate(page.summary),
        delegated=DelegatedFooterOut.model_validate(page.delegated),
    )


@client_contacts_router.post(
    "/{client_id}/contacts",
    action="contact.manage",
    response_model=ContactOut,
    status_code=201,
    errors=(409,),
)
async def create_contact_route(client_id: UUID, body: ContactIn, ctx: Ctx) -> ContactOut:
    """409 `contact_exists` for an email already on the client; one `contact.created` event."""
    await _gate(ctx)
    made = await service.create_contact(
        ctx,
        client_id,
        name=body.name,
        party_kind=body.party_kind,
        email=body.email,
        phone=body.phone,
        roles=_roles(body.roles),
    )
    return ContactOut(contact=_row(made.contact), version=made.version)


@contacts_router.get("/{contact_id}", action="contact.read", response_model=ContactDetailOut)
async def get_contact_route(contact_id: UUID, ctx: Ctx) -> ContactDetailOut:
    """The O2 drawer: roles, grants, sign-in history and delegated requests."""
    await _gate(ctx)
    return _detail(await service.contact_detail(ctx, contact_id))


@contacts_router.patch(
    "/{contact_id}", action="contact.manage", response_model=ContactOut, errors=(409,)
)
async def update_contact_route(contact_id: UUID, body: ContactPatchIn, ctx: Ctx) -> ContactOut:
    """409 `stale_version`; one `contact.updated` event naming the fields, never values. A new
    address revokes a pending invitation sent to the old one; 409 `contact_bound` for a contact
    that already signs in (its address is the person's own)."""
    await _gate(ctx)
    values: dict[str, str | None] = {}
    if body.name is not None:
        values["display_name"] = body.name
    if "email" in body.model_fields_set:
        values["email"] = body.email
    if "phone" in body.model_fields_set:
        values["phone"] = body.phone
    made = await service.update_contact(
        ctx,
        contact_id,
        seen_version=body.seen_version,
        values=values,
        roles=_roles(body.roles) if body.roles is not None else None,
    )
    return ContactOut(contact=_row(made.contact), version=made.version)


@contacts_router.post(
    "/{contact_id}/invitations",
    action="client_access.grant",
    response_model=InvitationOut,
    status_code=201,
    errors=(409,),
)
async def invite_contact_route(
    contact_id: UUID, body: InvitationIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> InvitationOut:
    """Human-only: pending grants and a single-use invitation in one unit of work and
    `contact.invited` emitted; 409 `gate_unmet` (G1) for a full-client grant before acceptance;
    422 `scope_outside_client`."""
    await _gate(ctx)
    asked = _asked(body.grants)
    await service.check_invite(ctx, contact_id, asked)  # before the replay lookup (ED-023)

    async def run() -> tuple[int, dict[str, object]]:
        made = await service.invite(ctx, contact_id, asked)
        return 201, _invitation(made).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="contacts.invite",
        key=idempotency_key,
        body={"contact_id": str(contact_id), **body.model_dump(mode="json")},
        run=run,
    )
    return InvitationOut.model_validate(stored.body)


@contact_invitations_router.post(
    "/{invitation_id}/resend",
    action="client_access.grant",
    response_model=InvitationOut,
    errors=(409,),
)
async def resend_invitation_route(invitation_id: UUID, ctx: Ctx) -> InvitationOut:
    """A new token; the old link stops working; `invitation.resent`."""
    await _gate(ctx)
    return _invitation(await service.resend(ctx, invitation_id))


@contact_invitations_router.post(
    "/{invitation_id}/revoke",
    action="client_access.revoke",
    response_model=InvitationRevokedOut,
)
async def revoke_invitation_route(invitation_id: UUID, ctx: Ctx) -> InvitationRevokedOut:
    """Human-only: grants revoked, sessions ended (`access.changed`), requests kept."""
    await _gate(ctx)
    done = await service.revoke(ctx, invitation_id)
    return InvitationRevokedOut.model_validate(asdict(done))


@contacts_router.put(
    "/{contact_id}/access",
    action="client_access.grant",
    response_model=ContactAccessOut,
    errors=(409,),
)
async def change_contact_access_route(
    contact_id: UUID, body: ContactAccessIn, ctx: Ctx
) -> ContactAccessOut:
    """CLI-04 e: the new grant set; 409 `stale_version`; `contact.access_changed`."""
    await _gate(ctx)
    changed = await service.change_access(ctx, contact_id, body.seen_version, _asked(body.grants))
    return ContactAccessOut(
        contact_id=changed.contact_id, grants=_grants(changed.grants), version=changed.version
    )


@contacts_router.post(
    "/{contact_id}/unlock",
    action="contact.unlock",
    response_model=ContactUnlockedOut,
    errors=(409,),
)
async def unlock_contact_route(contact_id: UUID, ctx: Ctx) -> ContactUnlockedOut:
    """Human-only: clears a portal lock (P-08 state); `contact.unlocked` audited."""
    await _gate(ctx)
    found, status, at = await service.unlock(ctx, contact_id)
    return ContactUnlockedOut(
        contact_id=found, portal_status=InvitationStatus(status), unlocked_at=at
    )


# --- P-08-T21: firm-side portal recovery (SPEC-320 AC-18, AC-19; C5 v1.1 portal half) ---------


async def _portal_gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, PORTAL_SIGN_IN_V2):
        raise NotFound("portal.sign_in_v2")


@client_contacts_router.post(
    "/{client_id}/contacts/{contact_id}/portal-unlock",
    action="contact.unlock",
    response_model=ContactPortalStatusOut,
    errors=(409,),
)
async def unlock_contact_portal_route(
    client_id: UUID, contact_id: UUID, ctx: Ctx
) -> ContactPortalStatusOut:
    """Clear a sign-in or two-step lock (fresh MFA). Audited `contact.unlocked` naming the person
    (INV-5); a walled client, or a contact of another client, answers 404 (INV-3); 409
    `factor_shared` when the person's locked factor is theirs in another firm too (the firm's
    sign-in lock is still cleared)."""
    await _portal_gate(ctx)
    done = await service.portal_unlock(ctx, client_id, contact_id)
    return ContactPortalStatusOut(
        client_id=client_id,
        contact_id=done.contact_id,
        portal_status=InvitationStatus(done.portal_state),
        locked_until=None,
    )


@client_contacts_router.post(
    "/{client_id}/contacts/{contact_id}/mfa-reset",
    action="contact.mfa_reset",
    response_model=ContactMfaResetOut,
    errors=(409,),
)
async def reset_contact_mfa_route(
    client_id: UUID, contact_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ContactMfaResetOut:
    """Remove the factor, the backup codes and the trusted devices and end the portal sessions;
    email the client in the firm's name. Security admin with fresh MFA. Audited
    `portal_mfa.reset`; the next sign-in goes to two-step setup. 409 `factor_shared` when the
    person belongs to another firm too: the factor stays, this firm's devices and sessions end,
    audited `portal_mfa.reset_refused`."""
    await _portal_gate(ctx)
    await service.check_mfa_reset(ctx, client_id, contact_id)  # before the replay lookup

    async def run() -> tuple[int, dict[str, object]]:
        done = await service.mfa_reset(ctx, client_id, contact_id)
        out = ContactMfaResetOut(
            client_id=client_id,
            contact_id=done.contact_id,
            mfa_enrolled=done.mfa_enrolled,
            trusted_devices_revoked=done.trusted_devices_revoked,
            reset_at=done.reset_at,
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="contacts.mfa_reset",
        key=idempotency_key,
        body={"client_id": str(client_id), "contact_id": str(contact_id)},
        run=run,
    )
    return ContactMfaResetOut.model_validate(stored.body)
