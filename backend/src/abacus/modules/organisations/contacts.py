"""CLI-04 contacts and portal access, live (P-07-T25; SPEC-321 Story 6; P-07 Story 2.1; DEC-300).

organisations owns the contact (its roles per entity, party kind, version and portal state);
identity owns the grants, the invitation and the portal lock (`identity.api` contact access);
requests records the delegated requests (C5, through identity's
`register_contact_delegations`).
Each write is one unit of work across the three.

- Every route finds the contact or client through `visible_clients(contact.read)`: a walled or
  unknown one is 404 (INV-3, DEC-43), and no count reveals it.
- A write is authorised on the client (`Resource.client`: firm admin, the derived
  `firm_partner`) or else on one of the client's open engagements where the caller holds an
  engagement role (engagement partner, manager, client service): the matrix's cells, which a
  firm-level resource alone can't reach.
- A full-client grant (`client` or `client_entity`) needs an engagement of the client at
  Accepted or later: 409 `gate_unmet` (G1) otherwise; that engagement is the invitation's.
- Revoking keeps the requests with the client: their delegation to the contact ends, nothing is
  reassigned or deleted (`kept_request_item_ids`).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.listing import Position, decode_cursor, encode_cursor, query_hash
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    ContactGrant,
    ContactGrantRow,
    Forbidden,
    GrantRole,
    Resource,
    ScopeKind,
    allowed_actions,
    authorise,
    authorise_grants,
    change_contact_grants,
    close_contact_invitations,
    contact_delegations_provider,
    engagement_resource,
    factor_enrolled,
    grants_of_contacts,
    invitation_contact,
    invitation_grants,
    invitations_of_contacts,
    invite_contact,
    locked_addresses,
    remove_provider_factor,
    resend_contact_invitation,
    reset_portal_mfa,
    revoke_contact,
    revoke_contact_links,
    scope_facts,
    sign_in_addresses,
    unlock_contact_sign_in,
    unlock_portal_mfa,
    visible_clients,
)
from abacus.modules.identity.api import GrantScopeOutsideClient as ScopeOutsideClient
from abacus.modules.organisations.events import ContactCreated
from abacus.modules.organisations.live import IllegalTransition, StaleVersion
from abacus.modules.organisations.models import Client, Contact
from abacus.modules.organisations.repository import (
    contact_roles_of,
    contacts_of,
    entities_of,
    get_contact,
    replace_contact_roles,
    set_portal_state,
    update_contact_versioned,
)
from abacus.modules.organisations.service import ContactExists, NewContact, add_contact
from abacus.modules.organisations.slots import fact_query

READ: Final = "contact.read"
ROW_ACTIONS: Final = ("contact.manage", "client_access.grant", "client_access.revoke")
ROW_ACTIONS_ALL: Final = (*ROW_ACTIONS, "contact.unlock")
# An engagement at Accepted or later (G1 met); prospects and closed engagements are not.
G1_MET: Final = ("active", "accepted", "contracted", "on_hold", "delivered")
_CLIENT_WIDE: Final = frozenset({"client", "client_entity"})
_PORTAL_ORDER: Final = {"active": 0, "invited": 1, "locked": 2, "not_invited": 3}


# A full-client grant before any engagement of the client is Accepted (G1). No docstring: the
# error catalogue keeps the engagement's summary for the shared code.
class GateUnmet(DomainConflict):
    code = "gate_unmet"


class FactorShared(DomainConflict):
    """P-08-T21 (DEC-329): the person's second factor is theirs in another firm too, so this
    firm can't reset or unlock it (this firm's devices and sessions still end). Platform support,
    or the person re-enrolling from their own account (POR-12), can."""

    code = "factor_shared"


class ContactBound(DomainConflict):
    """The contact signs in as a person already: the address is that person's own sign-in
    email, not the contact record's to change."""

    code = "contact_bound"


@dataclass(frozen=True)
class GrantAsked:
    """One grant of an O3 sheet: a role on a scope, limited to `request_item_ids` when given."""

    role: GrantRole
    scope_kind: ScopeKind
    scope_id: UUID
    request_item_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class RoleAsked:
    role: str
    scope_kind: str
    scope_id: UUID
    title_text: str | None = None


@dataclass(frozen=True)
class RoleView:
    role: str
    scope_kind: str
    scope_id: UUID
    scope_name: str
    title_text: str | None


@dataclass(frozen=True)
class RowView:
    id: UUID
    name: str
    party_kind: str
    email: str | None
    roles: list[RoleView]
    portal_status: str
    invited_on: date | None
    expires_on: date | None
    mfa_enrolled: bool | None
    last_seen_at: datetime | None
    delegated_request_count: int
    allowed_actions: list[str]


@dataclass(frozen=True)
class GrantView:
    id: UUID
    role: str
    scope_kind: str
    scope_id: UUID
    request_item_ids: list[UUID]
    status: str
    granted_at: datetime | None


@dataclass(frozen=True)
class PageView:
    items: list[RowView]
    next_cursor: str | None
    total: int
    counts: dict[str, int]
    summary: dict[str, int]
    delegated: dict[str, object]


@dataclass(frozen=True)
class DetailView:
    contact: RowView
    grants: list[GrantView]
    delegated_request_ids: list[UUID]
    version: int


@dataclass(frozen=True)
class InvitationView:
    invitation_id: UUID
    contact_id: UUID
    grants: list[GrantView]
    mfa_policy: str
    sent_at: datetime
    expires_at: datetime
    portal_status: str


@dataclass(frozen=True)
class RevokedView:
    invitation_id: UUID
    contact_id: UUID
    revoked_grant_ids: list[UUID]
    kept_request_item_ids: list[UUID]
    revoked_at: datetime


@dataclass(frozen=True)
class AccessView:
    contact_id: UUID
    grants: list[GrantView]
    version: int


# --- finding and authorising ------------------------------------------------------------------


async def _seen(session: AsyncSession, ctx: AuthContext, client_id: UUID) -> bool:
    seen = await visible_clients(ctx, READ, Client.id)
    found = await session.scalar(select(Client.id).where(Client.id == client_id, seen))
    return found is not None


async def _visible_contact(ctx: AuthContext, contact_id: UUID) -> Contact:
    async with tenant_session(ctx.tenant) as session:
        contact = await get_contact(session, contact_id)
        if contact is None or not await _seen(session, ctx, contact.client_id):
            raise NotFound("contact")
        return contact


async def _visible_client(ctx: AuthContext, client_id: UUID) -> None:
    async with tenant_session(ctx.tenant) as session:
        if not await _seen(session, ctx, client_id):
            raise NotFound("client")


async def _open_engagements(ctx: AuthContext, client_id: UUID) -> list[tuple[UUID, str]]:
    """The client's open engagements (engagements' registered fact), oldest first."""
    query = fact_query("engagements")
    if query is None:
        return []
    facts = query.subquery("client_engagements")
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(facts.c.engagement_id, facts.c.status)
            .where(facts.c.client_id == client_id)
            .order_by(facts.c.engagement_id)
        )
        return [(cast(UUID, r[0]), str(r[1])) for r in rows.all()]


async def _authorise_for_client(ctx: AuthContext, action: str, client_id: UUID) -> None:
    """On the client (firm roles), or else on an open engagement of it where the caller holds
    an engagement role; the first refusal when none allows it."""
    try:
        await authorise(ctx, action, Resource.client(ctx.tenant_id, client_id))
        return
    except Forbidden as refused:
        first = refused
    for engagement_id, _ in await _open_engagements(ctx, client_id):
        try:
            await authorise(ctx, action, await engagement_resource(ctx.tenant, engagement_id))
        except (Forbidden, NotFound):
            continue
        return
    raise first


async def _g1_engagement(ctx: AuthContext, client_id: UUID) -> UUID | None:
    met = [(G1_MET.index(s), e) for e, s in await _open_engagements(ctx, client_id) if s in G1_MET]
    return min(met)[1] if met else None


# --- grants asked -----------------------------------------------------------------------------


async def _expand(ctx: AuthContext, asked: Sequence[GrantAsked]) -> list[ContactGrant]:
    """Each asked grant as the grants it means: one per request it is limited to, which must lie
    within its scope; otherwise the one scope."""
    grants: list[ContactGrant] = []
    for grant in asked:
        if not grant.request_item_ids:
            grants.append(ContactGrant(grant.role, grant.scope_kind, grant.scope_id))
            continue
        if grant.scope_kind == "request_item":
            if grant.scope_id not in grant.request_item_ids:
                raise ScopeOutsideClient(facts={"scope_id": str(grant.scope_id)})
        else:
            container = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
            for item_id in grant.request_item_ids:
                item = await scope_facts(ctx.tenant, "request_item", item_id)
                if (
                    container is None
                    or item is None
                    or item.client_id != container.client_id
                    or (
                        container.engagement_id is not None
                        and item.engagement_id != container.engagement_id
                    )
                ):
                    raise ScopeOutsideClient(facts={"request_item_id": str(item_id)})
        grants.extend(
            ContactGrant(grant.role, "request_item", item_id)
            for item_id in dict.fromkeys(grant.request_item_ids)
        )
    return grants


def _grant_view(grant: ContactGrantRow) -> GrantView:
    return GrantView(
        grant.id,
        grant.role,
        grant.scope_kind,
        grant.scope_id,
        [grant.scope_id] if grant.scope_kind == "request_item" else [],
        grant.status if grant.status in ("pending", "active") else "revoked",
        grant.created_at,
    )


def _delegated(grants: Sequence[ContactGrantRow]) -> list[tuple[UUID, UUID]]:
    return [(g.id, g.scope_id) for g in grants if g.scope_kind == "request_item"]


# --- reads ------------------------------------------------------------------------------------


async def _live_delegations(
    ctx: AuthContext, contact_ids: Sequence[UUID]
) -> dict[UUID, tuple[tuple[UUID, ...], int]]:
    """Per contact, the delegated requests whose grant is still pending or active, and how many
    of them were received: a grant revoked elsewhere (its inviter offboarded) delegates
    nothing."""
    counted = await contact_delegations_provider().counts(ctx.tenant, contact_ids)
    live: dict[UUID, set[UUID]] = {}
    for grant in await grants_of_contacts(ctx.tenant, contact_ids):
        if grant.scope_kind == "request_item" and grant.status in ("pending", "active"):
            live.setdefault(grant.contact_id, set()).add(grant.scope_id)
    out: dict[UUID, tuple[tuple[UUID, ...], int]] = {}
    for contact, (items, received) in counted.items():
        held = live.get(contact, set())
        out[contact] = (
            tuple(i for i in items if i in held),
            len([i for i in received if i in held]),
        )
    return out


async def _rows(ctx: AuthContext, client_id: UUID, contacts: Sequence[Contact]) -> list[RowView]:
    ids = [c.id for c in contacts]
    async with tenant_session(ctx.tenant) as session:
        roles = await contact_roles_of(session, ids)
        entities = await entities_of(session, client_id)
        client = await session.scalar(select(Client.name).where(Client.id == client_id))
    invitations = await invitations_of_contacts(ctx.tenant, ids)
    # Locked follows where the person signs in, never the editable field (DEC-303).
    addresses = await sign_in_addresses(ctx.tenant, [(c.id, c.user_id) for c in contacts])
    locked = await locked_addresses(ctx.tenant, list(addresses.values()))
    counts = await _live_delegations(ctx, ids)
    actions = sorted(
        await allowed_actions(ctx, Resource.client(ctx.tenant_id, client_id), ROW_ACTIONS_ALL)
    )
    rows: list[RowView] = []
    for contact in contacts:
        state = contact.portal_state
        if state in ("active", "invited") and addresses.get(contact.id) in locked:
            state = "locked"
        invitation = invitations.get(contact.id)
        invited = state == "invited" and invitation is not None
        rows.append(
            RowView(
                contact.id,
                contact.display_name,
                contact.party_kind,
                contact.email,
                [
                    RoleView(
                        r.role,
                        r.scope_kind,
                        r.scope_id,
                        (client or "")
                        if r.scope_kind == "client"
                        else entities.get(r.scope_id, ""),
                        r.title_text,
                    )
                    for r in roles
                    if r.contact_id == contact.id
                ],
                state,
                cast(datetime, invitation["created_at"]).date()
                if invited and invitation
                else None,
                cast(datetime, invitation["expires_at"]).date()
                if invited and invitation
                else None,
                await factor_enrolled(contact.user_id) if contact.user_id is not None else None,
                None,  # P-08's sign-in history read is not yet a published identity read
                len(counts.get(contact.id, ((), 0))[0]),
                actions,
            )
        )
    return rows


def _sort_key(row: RowView, sort: str) -> tuple[str, str]:
    if sort == "portal_status":
        return (f"{_PORTAL_ORDER.get(row.portal_status, 9)}{row.name.casefold()}", str(row.id))
    if sort == "last_seen":
        return (row.last_seen_at.isoformat() if row.last_seen_at else "", str(row.id))
    return (row.name.casefold(), str(row.id))


async def list_contacts(
    ctx: AuthContext,
    client_id: UUID,
    *,
    portal_status: str | None,
    sort: str,
    cursor: str | None,
    limit: int,
) -> PageView:
    """CLI-04 a: the header counts and the footer cover the client's whole list (they are the
    client's, not the page's); `portal_status` filters the rows."""
    await _visible_client(ctx, client_id)
    async with tenant_session(ctx.tenant) as session:
        contacts = await contacts_of(session, client_id)
    rows = sorted(await _rows(ctx, client_id, contacts), key=lambda r: _sort_key(r, sort))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.portal_status] = counts.get(row.portal_status, 0) + 1
    summary = {k: counts.get(k, 0) for k in ("active", "invited", "not_invited", "locked")}
    delegated = await _live_delegations(ctx, [r.id for r in rows])
    parts = [r.delegated_request_count for r in rows if r.delegated_request_count]
    received = sum(delegated.get(r.id, ((), 0))[1] for r in rows)
    chosen = [r for r in rows if portal_status is None or r.portal_status == portal_status]
    query = query_hash(client=str(client_id), portal_status=portal_status, sort=sort)
    if cursor is not None:
        at = decode_cursor(cursor, tenant_id=ctx.tenant_id, resource="contacts", query=query)
        chosen = [r for r in chosen if _sort_key(r, sort) > (str(at.key), at.id)]
    page = chosen[:limit]
    following = None
    if len(chosen) > limit:
        key, last = _sort_key(page[-1], sort)
        following = encode_cursor(
            Position(key, last), tenant_id=ctx.tenant_id, resource="contacts", query=query
        )
    return PageView(
        page,
        following,
        len([r for r in rows if portal_status is None or r.portal_status == portal_status]),
        counts,
        summary,
        {"parts": parts, "total": sum(parts), "received": received},
    )


async def contact_detail(ctx: AuthContext, contact_id: UUID) -> DetailView:
    """The O2 drawer."""
    contact = await _visible_contact(ctx, contact_id)
    (row,) = await _rows(ctx, contact.client_id, [contact])
    grants = await grants_of_contacts(ctx.tenant, [contact.id])
    counts = await _live_delegations(ctx, [contact.id])
    return DetailView(
        row,
        [_grant_view(g) for g in grants],
        list(counts.get(contact.id, ((), 0))[0]),
        contact.version,
    )


# --- contact create and edit ------------------------------------------------------------------


async def _check_roles(ctx: AuthContext, client_id: UUID, roles: Sequence[RoleAsked]) -> None:
    async with tenant_session(ctx.tenant) as session:
        entities = await entities_of(session, client_id)
    for role in roles:
        if (role.scope_kind == "client" and role.scope_id != client_id) or (
            role.scope_kind == "client_entity" and role.scope_id not in entities
        ):
            raise ScopeOutsideClient(facts={"scope_id": str(role.scope_id)})


def _roles(roles: Sequence[RoleAsked]) -> list[tuple[str, str, UUID, str | None]]:
    return list(dict.fromkeys((r.role, r.scope_kind, r.scope_id, r.title_text) for r in roles))


async def create_contact(
    ctx: AuthContext,
    client_id: UUID,
    *,
    name: str,
    party_kind: str,
    email: str | None,
    phone: str | None,
    roles: Sequence[RoleAsked],
) -> DetailView:
    await _visible_client(ctx, client_id)
    await _authorise_for_client(ctx, "contact.manage", client_id)
    await _check_roles(ctx, client_id, roles)
    async with uow(ctx.tenant) as tx:
        contact_id = await add_contact(
            tx,
            ctx.tenant_id,
            client_id,
            NewContact(name, "client_person", email=email, phone=phone, party_kind=party_kind),
        )
        await replace_contact_roles(tx.session, ctx.tenant_id, contact_id, _roles(roles))
        tx.emit(ContactCreated(client_id=client_id, contact_id=contact_id))
    return await contact_detail(ctx, contact_id)


async def update_contact(
    ctx: AuthContext,
    contact_id: UUID,
    *,
    seen_version: int,
    values: dict[str, str | None],
    roles: Sequence[RoleAsked] | None,
) -> DetailView:
    """Absent fields unchanged; `roles` replaces. 409 `stale_version` for an old version."""
    contact = await _visible_contact(ctx, contact_id)
    await _authorise_for_client(ctx, "contact.manage", contact.client_id)
    if roles is not None:
        await _check_roles(ctx, contact.client_id, roles)
    names: list[str] = sorted(values) + (["roles"] if roles is not None else [])
    readdressed = (
        "email" in values
        and (values["email"] or "").strip().lower() != (contact.email or "").strip().lower()
    )
    if readdressed and contact.user_id is not None:
        raise ContactBound  # the person's identity email is the address (DEC-303)
    async with uow(ctx.tenant) as tx:
        try:
            async with tx.session.begin_nested():
                moved = await update_contact_versioned(
                    tx.session, contact_id, seen_version, values
                )
        except IntegrityError as exc:  # a unique email on the client
            if "contacts_one_email" in str(exc.orig):
                raise ContactExists from None
            raise
        if moved is None:
            raise StaleVersion(facts={"contact_id": str(contact_id)})
        if roles is not None:
            await replace_contact_roles(tx.session, ctx.tenant_id, contact_id, _roles(roles))
        if readdressed:
            # The link went to the old address: it dies, with its pending grants (DEC-303).
            closed = await close_contact_invitations(tx, ctx, contact_id)
            if closed:
                await contact_delegations_provider().end(tx, closed)
            await revoke_contact_links(tx, [contact_id])  # P-08-T21: its links went there too
            if contact.portal_state == "invited":
                await set_portal_state(tx.session, contact_id, "not_invited")
        tx.record(
            "contact.updated",
            target=Target("client", contact.client_id),
            after=Ref(contact_id=contact_id, **dict.fromkeys(names, 1)),  # names, never values
        )
    return await contact_detail(ctx, contact_id)


# --- invitations and access -------------------------------------------------------------------


async def _invitable(ctx: AuthContext, contact_id: UUID) -> Contact:
    contact = await _visible_contact(ctx, contact_id)
    if contact.portal_state in ("active", "locked"):
        raise IllegalTransition  # an active contact's access changes through "Change scope"
    return contact


async def check_invite(ctx: AuthContext, contact_id: UUID, asked: Sequence[GrantAsked]) -> None:
    """Before the idempotency lookup: the contact visible and every grant the caller's to give."""
    contact = await _invitable(ctx, contact_id)
    await authorise_grants(ctx, contact.client_id, await _expand(ctx, asked))


async def invite(
    ctx: AuthContext, contact_id: UUID, asked: Sequence[GrantAsked]
) -> InvitationView:
    """CLI-04 b: pending grants, a single-use 14-day invitation and the delegations, in one unit
    of work; `contact.invited`; the email goes out from the firm's Invitation template."""
    contact = await _invitable(ctx, contact_id)
    grants = await _expand(ctx, asked)
    anchor = None
    if any(g.scope_kind in _CLIENT_WIDE for g in grants):
        anchor = await _g1_engagement(ctx, contact.client_id)
        if anchor is None:
            raise GateUnmet(facts={"gate": "G1", "client_id": str(contact.client_id)})
    async with uow(ctx.tenant) as tx:
        made = await invite_contact(
            tx,
            ctx,
            client_id=contact.client_id,
            contact_id=contact.id,
            email=contact.email or "",
            grants=grants,
            client_wide_engagement=anchor,
        )
        provider = contact_delegations_provider()
        # An earlier invitation's grants, closed now or by its inviter's offboarding, end their
        # delegations (only open ones are touched).
        stale = [g.id for g in await grants_of_contacts(ctx.tenant, [contact.id])]
        await provider.end(tx, [*made.closed_grant_ids, *stale])
        delegated = _delegated(made.grants)
        if delegated:
            await provider.record(tx, contact.id, delegated, ctx.user_id)
        await set_portal_state(tx.session, contact.id, "invited")
    return InvitationView(
        made.invitation_id,
        contact.id,
        [_grant_view(g) for g in made.grants],
        made.mfa_policy,
        made.sent_at,
        made.expires_at,
        "invited",
    )


async def _invitation_contact(ctx: AuthContext, invitation_id: UUID) -> Contact:
    contact_id = await invitation_contact(ctx.tenant, invitation_id)
    if contact_id is None:
        raise NotFound("client_invitation")
    try:
        return await _visible_contact(ctx, contact_id)
    except NotFound:
        raise NotFound("client_invitation") from None


async def resend(ctx: AuthContext, invitation_id: UUID) -> InvitationView:
    """A new link and 14 days, after the checks the invitation passed: G1 again for a
    client-wide grant (DEC-303), and every grant still pending (identity)."""
    contact = await _invitation_contact(ctx, invitation_id)
    grants = await invitation_grants(ctx.tenant, invitation_id)
    if any(g.scope_kind in _CLIENT_WIDE for g in grants) and (
        await _g1_engagement(ctx, contact.client_id) is None
    ):
        raise GateUnmet(facts={"gate": "G1", "client_id": str(contact.client_id)})
    async with uow(ctx.tenant) as tx:
        made = await resend_contact_invitation(tx, ctx, contact.client_id, invitation_id)
    return InvitationView(
        invitation_id,
        contact.id,
        [_grant_view(g) for g in made.grants],
        made.mfa_policy,
        made.sent_at,
        made.expires_at,
        "invited",
    )


async def revoke(ctx: AuthContext, invitation_id: UUID) -> RevokedView:
    """CLI-04 f: grants revoked, sessions ended, the delegations ended and the requests kept."""
    contact = await _invitation_contact(ctx, invitation_id)
    async with uow(ctx.tenant) as tx:
        done = await revoke_contact(tx, ctx, contact.client_id, invitation_id)
        ended = await contact_delegations_provider().end(tx, [g.id for g in done.revoked])
        await set_portal_state(tx.session, contact.id, "not_invited")
        await revoke_contact_links(tx, [contact.id])  # P-08-T21: no link outlives the access
    kept = list(dict.fromkeys([*(item for _, item in _delegated(done.revoked)), *ended]))
    return RevokedView(
        invitation_id,
        contact.id,
        [g.id for g in done.revoked],
        kept,
        await clock.now(ctx.tenant),
    )


async def change_access(
    ctx: AuthContext, contact_id: UUID, seen_version: int, asked: Sequence[GrantAsked]
) -> AccessView:
    """CLI-04 e: the whole grant set after the change; 409 `stale_version`."""
    contact = await _visible_contact(ctx, contact_id)
    if contact.portal_state not in ("active", "invited", "locked"):
        raise IllegalTransition
    grants = await _expand(ctx, asked)
    if any(g.scope_kind in _CLIENT_WIDE for g in grants) and (
        await _g1_engagement(ctx, contact.client_id) is None
    ):
        raise GateUnmet(facts={"gate": "G1", "client_id": str(contact.client_id)})
    active = contact.portal_state in ("active", "locked") and contact.user_id is not None
    async with uow(ctx.tenant) as tx:
        version = await update_contact_versioned(tx.session, contact.id, seen_version, {})
        if version is None:
            raise StaleVersion(facts={"contact_id": str(contact.id)})
        changed = await change_contact_grants(
            tx,
            ctx,
            client_id=contact.client_id,
            contact_id=contact.id,
            user_id=contact.user_id if active else None,
            grants=grants,
        )
        provider = contact_delegations_provider()
        if changed.removed:
            await provider.end(tx, [g.id for g in changed.removed])
        delegated = _delegated(changed.added)
        if delegated:
            await provider.record(tx, contact.id, delegated, ctx.user_id)
    return AccessView(contact.id, [_grant_view(g) for g in changed.grants], version)


async def unlock(ctx: AuthContext, contact_id: UUID) -> tuple[UUID, str, datetime]:
    """CLI-04 d: the portal lock on the contact's address cleared; `contact.unlocked`. IT /
    Security unlocks without reading contacts (`contact.unlock` is theirs, `contact.read` not),
    so the contact is found by id and a wall answers 404 as everywhere else."""
    async with tenant_session(ctx.tenant) as session:
        contact = await get_contact(session, contact_id)
    if contact is None:
        raise NotFound("contact")
    try:
        await _authorise_for_client(ctx, "contact.unlock", contact.client_id)
    except Forbidden as refused:
        if refused.layer == "wall":
            raise NotFound("contact") from None
        raise
    address = (await sign_in_addresses(ctx.tenant, [(contact.id, contact.user_id)])).get(
        contact.id
    )
    async with uow(ctx.tenant) as tx:
        await unlock_contact_sign_in(
            tx, ctx, client_id=contact.client_id, contact_id=contact.id, email=address
        )
        factor = await unlock_portal_mfa(tx, ctx, contact.user_id)  # P-08-T21: second step too
        _refused_if_shared(tx, contact, factor)
    if factor == "shared":
        raise FactorShared(facts={"contact_id": str(contact.id)})
    return contact.id, contact.portal_state, await clock.now(ctx.tenant)


# --- P-08-T21: firm-side portal recovery on the client's own path (SPEC-320 AC-18, AC-19) ------


@dataclass(frozen=True)
class PortalUnlocked:
    contact_id: UUID
    portal_state: str


@dataclass(frozen=True)
class MfaResetView:
    contact_id: UUID
    mfa_enrolled: bool
    trusted_devices_revoked: int
    reset_at: datetime


async def _client_contact(
    ctx: AuthContext, action: str, client_id: UUID, contact_id: UUID
) -> Contact:
    """The client's contact once `action` is authorised on the client; a contact of another
    client, an unknown one and a wall all answer the same 404 (INV-3)."""
    async with tenant_session(ctx.tenant) as session:
        contact = await get_contact(session, contact_id)
    if contact is None or contact.client_id != client_id:
        raise NotFound("contact")
    try:
        await _authorise_for_client(ctx, action, contact.client_id)
    except Forbidden as refused:
        if refused.layer == "wall":
            raise NotFound("contact") from None
        raise
    return contact


async def portal_unlock(ctx: AuthContext, client_id: UUID, contact_id: UUID) -> PortalUnlocked:
    """Story 7.1: the firm's sign-in lock on where the contact signs in (DEC-303) and the second-
    step lock on their factor, cleared in one unit of work; `contact.unlocked` names the person
    who unlocked (INV-5)."""
    contact = await _client_contact(ctx, "contact.unlock", client_id, contact_id)
    address = (await sign_in_addresses(ctx.tenant, [(contact.id, contact.user_id)])).get(
        contact.id
    )
    async with uow(ctx.tenant) as tx:
        await unlock_contact_sign_in(
            tx, ctx, client_id=contact.client_id, contact_id=contact.id, email=address
        )
        factor = await unlock_portal_mfa(tx, ctx, contact.user_id)
        _refused_if_shared(tx, contact, factor)
    if factor == "shared":
        raise FactorShared(facts={"contact_id": str(contact.id)})
    return PortalUnlocked(contact.id, contact.portal_state)


def _refused_if_shared(tx: UnitOfWork, contact: Contact, factor: str) -> None:
    """The sign-in lock is the firm's and was cleared; the factor's lock is the person's across
    firms and stays (DEC-329): audited as a refusal beside `contact.unlocked`."""
    if factor == "shared":
        tx.record(
            "portal_mfa.unlock_refused",
            target=Target("client", contact.client_id),
            after=Ref(contact_id=contact.id),
        )


async def check_mfa_reset(ctx: AuthContext, client_id: UUID, contact_id: UUID) -> None:
    """Before the idempotency lookup (ED-023's shape): a replay is checked like the first call."""
    await _client_contact(ctx, "contact.mfa_reset", client_id, contact_id)


async def mfa_reset(ctx: AuthContext, client_id: UUID, contact_id: UUID) -> MfaResetView:
    """Story 7.2: the contact's person's factor, backup codes, trusted devices and portal
    sessions here, removed in one unit of work with `portal_mfa.reset`; the notice email and the
    provider's copy of the factor follow."""
    contact = await _client_contact(ctx, "contact.mfa_reset", client_id, contact_id)
    async with uow(ctx.tenant) as tx:
        done = await reset_portal_mfa(
            tx, ctx, client_id=contact.client_id, contact_id=contact.id, user_id=contact.user_id
        )
    if done.shared:
        raise FactorShared(
            facts={
                "contact_id": str(contact.id),
                "trusted_devices_revoked": done.devices_revoked,
                "sessions_ended": done.sessions_ended,
            }
        )
    await remove_provider_factor(done.factor_ref)
    return MfaResetView(contact.id, False, done.devices_revoked, await clock.now(ctx.tenant))


async def contact_portal_facts(
    tenant: TenantContext, contact_id: UUID
) -> tuple[str, UUID | None, str | None] | None:
    """P-08-T21: a contact's portal state, person and sign-in address (DEC-303: the person's
    identity email, else the live invitation's), for communications' link renewal; None for a
    contact the firm doesn't have."""
    async with tenant_session(tenant) as session:
        contact = await get_contact(session, contact_id)
    if contact is None:
        return None
    address = (await sign_in_addresses(tenant, [(contact.id, contact.user_id)])).get(contact.id)
    return contact.portal_state, contact.user_id, address
