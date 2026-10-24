"""A client contact's portal access (P-07-T25; SPEC-321 Story 6; P-07 Story 2.1; DEC-300).
PROTECTED.

CLI-04's writes on identity's side, each inside the caller's unit of work (organisations owns the
contact and orchestrates; requests records the delegations):

- `invite_contact`: every grant authorised (`client_access.grant`, fresh MFA, G2 for the acting
  member on attest clients) on its own resource, then pending grants (no person yet) and an
  invitations-v2 row carrying their ids (`grant_ids`), 14 days, single use; the contact's earlier
  pending invitation and its pending grants are closed. `contact.invited` is emitted, and
  `client_invitation.issued` so the email goes out with a fresh token.
- `resend_contact_invitation`: the grants re-authorised now, a fresh 14 days, the old link dead
  at once (its token dropped), a new one at delivery.
- `revoke_contact`: every live grant of the contact revoked (`client_access.revoke`), the pending
  invitation and its link dead, and the person's portal sessions and trusted devices ended in the
  same transaction (with `access.changed` for every other holder). Nothing about the requests
  changes: the caller reports them kept.
- `change_contact_grants`: the grant set replaced, the diff authorised (`client_access.grant` on
  every resource touched, `client_access.revoke` on what goes). For an active person the new
  grants are theirs at once; for an invited contact they join the pending invitation.
- `unlock_contact_sign_in`: the firm's portal sign-in lock on the contact's address cleared
  (`contact.unlock`); staff locks are never touched here (DF-24).

Every write is a person's (INV-1): agent, system and support contexts are refused before
anything else, as the matrix also denies them. Acceptance (`invitations._accept_in`) activates
exactly the pending grants named on the invitation, re-checking the inviter (DEC-277).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.identity.authz import Forbidden, Resource, authorise
from abacus.modules.identity.client_access import (
    GRANT_ROLES,
    SCOPE_KINDS,
    GrantRole,
    ScopeKind,
    grant_in_unit_of_work,
)
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import (
    AccessChanged,
    ClientAccessRevoked,
    ClientInvitationIssued,
    ContactInvited,
)
from abacus.modules.identity.invitations import (
    INVITATION_DAYS,
    InvitationInvalid,
    create_invitation,
    grant_resource,
)
from abacus.modules.identity.mfa_floor import portal_security_policy
from abacus.modules.identity.portal_mfa import record_revoked
from abacus.modules.identity.repository import (
    ContactGrantRow,
    contact_grants,
    contact_invitations,
    end_portal_access,
    extend_invitation,
    get_invitation,
    grants_by_id,
    insert_grant_event,
    insert_pending_grant,
    locked_emails,
    set_grant_status,
    set_invitation_grants,
    set_invitation_status,
    set_token_hash,
    unlock_sign_in,
)

MAX_GRANTS: Final = 200
_LIVE: Final = frozenset({"pending", "active"})
MfaPolicy = Literal["required_by_firm", "optional"]


class ScopeOutsideClient(DomainInvalid):
    """A grant's scope, or a delegated request, is not the contact's client's."""

    code = "scope_outside_client"


@dataclass(frozen=True)
class ContactGrant:
    """One grant asked for: a role on one scope."""

    role: GrantRole
    scope_kind: ScopeKind
    scope_id: UUID


@dataclass(frozen=True)
class ContactInvitation:
    invitation_id: UUID
    contact_id: UUID
    engagement_id: UUID
    grants: tuple[ContactGrantRow, ...]
    sent_at: datetime
    expires_at: datetime
    mfa_policy: MfaPolicy
    closed_grant_ids: tuple[UUID, ...] = ()  # an earlier invitation's pending grants, closed


@dataclass(frozen=True)
class RevokedContact:
    invitation_id: UUID | None
    revoked: tuple[ContactGrantRow, ...]


@dataclass(frozen=True)
class ChangedGrants:
    added: tuple[ContactGrantRow, ...]
    removed: tuple[ContactGrantRow, ...]
    grants: tuple[ContactGrantRow, ...]


def _human(ctx: AuthContext, action: str) -> None:
    """INV-1: a person's own act, never an agent, the platform or a support session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _key(grant: ContactGrant | ContactGrantRow) -> tuple[str, str, UUID]:
    return (grant.role, grant.scope_kind, grant.scope_id)


async def _resources(
    tenant: TenantContext, client_id: UUID, grants: Sequence[ContactGrant | ContactGrantRow]
) -> list[Resource]:
    """Each grant's resource, in order; `ScopeOutsideClient` for a scope that isn't the client's
    (or resolves to nothing: an unknown kind fails closed)."""
    found: list[Resource] = []
    for grant in grants:
        if grant.role not in GRANT_ROLES or grant.scope_kind not in SCOPE_KINDS:
            raise ScopeOutsideClient(facts={"scope_kind": grant.scope_kind})
        resolved = await grant_resource(tenant, grant.scope_kind, grant.scope_id)
        if resolved is None or resolved[1] != client_id:
            raise ScopeOutsideClient(
                facts={"scope_kind": grant.scope_kind, "scope_id": str(grant.scope_id)}
            )
        found.append(resolved[0])
    return found


async def _authorise_each(ctx: AuthContext, action: str, resources: Sequence[Resource]) -> None:
    seen: set[tuple[UUID | None, UUID | None]] = set()
    for resource in resources:
        key = (resource.engagement_id, resource.client_id)
        if key not in seen:
            await authorise(ctx, action, resource)
            seen.add(key)


def _valid(grants: Sequence[ContactGrant]) -> None:
    keys = [_key(g) for g in grants]
    if not 1 <= len(keys) <= MAX_GRANTS or len(set(keys)) != len(keys):
        raise InvitationInvalid("grants")


async def mfa_policy(tenant_id: UUID, roles: Sequence[str]) -> MfaPolicy:
    """What O3 shows: required when the firm asks it of every client user or an owner grant
    brings the person under the floor (DEC-34); otherwise optional."""
    policy = await portal_security_policy(tenant_id)
    if policy.mfa_for_all_client_users or "owner" in roles:
        return "required_by_firm"
    return "optional"


async def _close_pending(tx: UnitOfWork, tenant_id: UUID, contact_id: UUID) -> list[UUID]:
    """The contact's pending invitations revoked with their links, and their pending grants
    closed: one live invitation per contact. Returns the grants closed."""
    closed: list[UUID] = []
    for row in await contact_invitations(tx.session, [contact_id], lock=True):
        if row["status"] != "pending":
            continue
        invitation_id = cast(UUID, row["id"])
        await set_invitation_status(tx.session, invitation_id, "revoked")
        await set_token_hash(tx.session, invitation_id, None)
        tx.record("client_invitation.revoked", target=Target("client_invitation", invitation_id))
        raw = cast(list[UUID] | None, row["grant_ids"]) or []
        for grant in await grants_by_id(tx.session, [UUID(str(g)) for g in raw], lock=True):
            if grant.status == "pending" and await set_grant_status(
                tx.session, grant.id, "revoked"
            ):
                await insert_grant_event(
                    tx.session,
                    tenant_id=tenant_id,
                    grant_id=grant.id,
                    event="revoked",
                    by=None,
                )
                closed.append(grant.id)
    return closed


def _anchor(resources: Sequence[Resource], client_wide_engagement: UUID | None) -> UUID:
    """The invitation's engagement (DEC-300): the one its engagement-bound grants lie in, or the
    client's engagement that met G1 when every grant is client-wide."""
    engagements = {r.engagement_id for r in resources if r.engagement_id is not None}
    if len(engagements) > 1:
        raise InvitationInvalid("grants")
    if engagements:
        return next(iter(engagements))
    if client_wide_engagement is None:
        raise InvitationInvalid("grants")
    return client_wide_engagement


async def _insert_pending(
    tx: UnitOfWork, ctx: AuthContext, contact_id: UUID, grants: Sequence[ContactGrant]
) -> list[UUID]:
    ids: list[UUID] = []
    for grant in grants:
        grant_id = await insert_pending_grant(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "contact_id": contact_id,
                "role": grant.role,
                "scope_kind": grant.scope_kind,
                "scope_id": grant.scope_id,
                "granted_by": ctx.user_id,
            },
        )
        await insert_grant_event(
            tx.session, tenant_id=ctx.tenant_id, grant_id=grant_id, event="granted", by=ctx.user_id
        )
        ids.append(grant_id)
    return ids


async def invite_contact(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    client_id: UUID,
    contact_id: UUID,
    email: str,
    grants: Sequence[ContactGrant],
    client_wide_engagement: UUID | None,
) -> ContactInvitation:
    """CLI-04 b. The caller (organisations) has found the contact visible, checked G1 for
    client-wide grants and passes the engagement that met it."""
    _human(ctx, "client_access.grant")
    _valid(grants)
    resources = await _resources(ctx.tenant, client_id, grants)
    await _authorise_each(ctx, "client_access.grant", resources)
    engagement_id = _anchor(resources, client_wide_engagement)
    closed = await _close_pending(tx, ctx.tenant_id, contact_id)
    grant_ids = await _insert_pending(tx, ctx, contact_id, grants)
    roles = {g.role for g in grants}
    invitation_id = await create_invitation(
        tx,
        ctx,
        engagement_id,
        email,
        "client_admin" if "owner" in roles else "client_contributor",
        kind="outside_org"
        if "third_party" in roles
        else "delegate"
        if "delegate" in roles
        else "firm_invite",
        contact_id=contact_id,
        grant_ids=grant_ids,
    )
    tx.emit(
        ContactInvited(contact_id=contact_id, invitation_id=invitation_id, grant_ids=grant_ids)
    )
    tx.record(
        "contact.invited",
        target=Target("client", client_id),
        after=Ref(contact_id=contact_id, invitation_id=invitation_id, grants=len(grant_ids)),
    )
    row = await get_invitation(tx.session, invitation_id)
    if row is None:  # written above, in this transaction
        raise NotFound("client_invitation")
    return ContactInvitation(
        invitation_id,
        contact_id,
        engagement_id,
        tuple(await grants_by_id(tx.session, grant_ids)),
        cast(datetime, row["created_at"]),
        cast(datetime, row["expires_at"]),
        await mfa_policy(ctx.tenant_id, sorted(roles)),
        tuple(closed),
    )


async def _invitation(tx: UnitOfWork, invitation_id: UUID) -> tuple[dict[str, object], UUID]:
    row = await get_invitation(tx.session, invitation_id, lock=True)
    if row is None or row["grant_ids"] is None or row["contact_id"] is None:
        raise NotFound("client_invitation")
    return dict(row), cast(UUID, row["contact_id"])


async def resend_contact_invitation(
    tx: UnitOfWork, ctx: AuthContext, client_id: UUID, invitation_id: UUID
) -> ContactInvitation:
    """A fresh 14 days and a new link; the old link stops working now (Q-03-T007). Only a
    pending invitation (expired included: resending is how an expired link is renewed)."""
    _human(ctx, "client_access.grant")
    row, contact_id = await _invitation(tx, invitation_id)
    if row["status"] != "pending":
        raise NotFound("client_invitation")
    raw = cast(list[UUID], row["grant_ids"])
    grants = await grants_by_id(tx.session, [UUID(str(g)) for g in raw], lock=True)
    await _authorise_each(
        ctx, "client_access.grant", await _resources(ctx.tenant, client_id, grants)
    )
    await extend_invitation(tx.session, invitation_id, INVITATION_DAYS)
    await set_token_hash(tx.session, invitation_id, None)
    tx.record("invitation.resent", target=Target("client_invitation", invitation_id))
    tx.emit(ClientInvitationIssued(invitation_id=invitation_id))
    fresh = await get_invitation(tx.session, invitation_id)
    if fresh is None:
        raise NotFound("client_invitation")
    return ContactInvitation(
        invitation_id,
        contact_id,
        cast(UUID, row["engagement_id"]),
        tuple(grants),
        system_now(),
        cast(datetime, fresh["expires_at"]),
        await mfa_policy(ctx.tenant_id, sorted({g.role for g in grants})),
    )


async def _end_sessions(tx: UnitOfWork, ctx: AuthContext, users: set[UUID]) -> None:
    """The people's portal sessions and trusted devices in the firm end now, in this
    transaction; `access.changed` tells every other holder of their access."""
    for user in sorted(users):
        record_revoked(tx, user, await end_portal_access(tx.session, ctx.tenant_id, user))
        tx.emit(AccessChanged(user_id=user))


async def _revoke_grants(
    tx: UnitOfWork, ctx: AuthContext, grants: Sequence[ContactGrantRow]
) -> tuple[list[ContactGrantRow], set[UUID]]:
    revoked: list[ContactGrantRow] = []
    users: set[UUID] = set()
    for grant in grants:
        if not await set_grant_status(tx.session, grant.id, "revoked"):
            continue
        await insert_grant_event(
            tx.session, tenant_id=ctx.tenant_id, grant_id=grant.id, event="revoked", by=ctx.user_id
        )
        if grant.user_id is not None:
            tx.emit(ClientAccessRevoked(grant_id=grant.id, user_id=grant.user_id))
            users.add(grant.user_id)
        revoked.append(grant)
    return revoked, users


async def revoke_contact(
    tx: UnitOfWork, ctx: AuthContext, client_id: UUID, invitation_id: UUID
) -> RevokedContact:
    """CLI-04 f, from the contact's invitation: every live grant of the contact revoked, the
    invitation's link dead, sessions ended. The requests are not touched (DEC-300)."""
    _human(ctx, "client_access.revoke")
    row, contact_id = await _invitation(tx, invitation_id)
    if row["status"] not in ("pending", "accepted"):
        raise NotFound("client_invitation")
    live = [g for g in await contact_grants(tx.session, [contact_id]) if g.status in _LIVE]
    if not live and row["status"] != "pending":
        raise NotFound("client_invitation")
    resources = await _resources(ctx.tenant, client_id, live) if live else []
    if not resources:
        resources = [Resource.client(ctx.tenant_id, client_id)]
    await _authorise_each(ctx, "client_access.revoke", resources)
    if row["status"] == "pending":
        await set_invitation_status(tx.session, invitation_id, "revoked")
        await set_token_hash(tx.session, invitation_id, None)
    revoked, users = await _revoke_grants(
        tx, ctx, await grants_by_id(tx.session, [g.id for g in live], lock=True)
    )
    await _end_sessions(tx, ctx, users)
    tx.record("invitation.revoked", target=Target("client_invitation", invitation_id))
    if revoked:
        tx.record("client_access.revoked", target=Target("client", client_id))
    return RevokedContact(invitation_id, tuple(revoked))


async def change_contact_grants(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    client_id: UUID,
    contact_id: UUID,
    user_id: UUID | None,
    grants: Sequence[ContactGrant],
) -> ChangedGrants:
    """CLI-04 e: the contact's live grant set becomes `grants`. An active person (`user_id`)
    holds the new grants at once; an invited contact's join its pending invitation, whose
    engagement they must lie in (or be client-wide)."""
    _human(ctx, "client_access.grant")
    keys = [_key(g) for g in grants]
    if len(keys) > MAX_GRANTS or len(set(keys)) != len(keys):
        raise InvitationInvalid("grants")
    current = [g for g in await contact_grants(tx.session, [contact_id]) if g.status in _LIVE]
    wanted = set(keys)
    removed = [g for g in current if _key(g) not in wanted]
    held = {_key(g) for g in current}
    added = [g for g in grants if _key(g) not in held]
    add_resources = await _resources(ctx.tenant, client_id, added)
    remove_resources = await _resources(ctx.tenant, client_id, removed) if removed else []
    touched = [*add_resources, *remove_resources] or (
        await _resources(ctx.tenant, client_id, current) if current else []
    )
    await _authorise_each(
        ctx, "client_access.grant", touched or [Resource.client(ctx.tenant_id, client_id)]
    )
    await _authorise_each(ctx, "client_access.revoke", remove_resources)
    pending = next(
        (
            r
            for r in await contact_invitations(tx.session, [contact_id], lock=True)
            if r["status"] == "pending" and r["grant_ids"] is not None
        ),
        None,
    )
    if user_id is None and pending is None:
        raise InvitationInvalid("contact")
    gone, users = await _revoke_grants(
        tx, ctx, await grants_by_id(tx.session, [g.id for g in removed], lock=True)
    )
    new_ids: list[UUID] = []
    if user_id is not None:
        for grant, resource in zip(added, add_resources, strict=True):
            made = await grant_in_unit_of_work(
                tx,
                tenant_id=ctx.tenant_id,
                target=Target("engagement", resource.engagement_id)
                if resource.engagement_id is not None
                else Target("firm", ctx.tenant_id),
                user_id=user_id,
                role=grant.role,
                scope_kind=grant.scope_kind,
                scope_id=grant.scope_id,
                granted_by=ctx.user_id,
                contact_id=contact_id,
            )
            if made is not None:
                new_ids.append(made)
        if added or gone:
            users.add(user_id)
    elif pending is not None:
        anchor = cast(UUID, pending["engagement_id"])
        if any(r.engagement_id not in (None, anchor) for r in add_resources):
            raise InvitationInvalid("grants")
        new_ids = await _insert_pending(tx, ctx, contact_id, added)
        gone_ids = {g.id for g in gone}
        kept = [UUID(str(g)) for g in cast(list[UUID], pending["grant_ids"])]
        remaining = [g for g in kept if g not in gone_ids] + new_ids
        invitation_id = cast(UUID, pending["id"])
        if remaining:
            await set_invitation_grants(tx.session, invitation_id, remaining)
        else:  # nothing left to grant: the invitation goes with its link
            await set_invitation_status(tx.session, invitation_id, "revoked")
            await set_token_hash(tx.session, invitation_id, None)
            tx.record(
                "client_invitation.revoked", target=Target("client_invitation", invitation_id)
            )
    if gone:
        await _end_sessions(tx, ctx, users)
    elif user_id is not None and added:
        tx.emit(AccessChanged(user_id=user_id))
    tx.record(
        "contact.access_changed",
        target=Target("client", client_id),
        after=Ref(contact_id=contact_id, added=len(new_ids), removed=len(gone)),
    )
    after = await contact_grants(tx.session, [contact_id])
    return ChangedGrants(tuple(await grants_by_id(tx.session, new_ids)), tuple(gone), tuple(after))


async def unlock_contact_sign_in(
    tx: UnitOfWork, ctx: AuthContext, *, client_id: UUID, contact_id: UUID, email: str | None
) -> bool:
    """CLI-04 d, after the caller authorised `contact.unlock` for this client: the portal lock
    on the contact's address cleared. Whether there was one; audited either way."""
    _human(ctx, "contact.unlock")
    cleared = email is not None and await unlock_sign_in(tx.session, email)
    tx.record(
        "contact.unlocked",
        target=Target("client", client_id),
        after=Ref(contact_id=contact_id, cleared=int(cleared)),
    )
    return cleared


async def locked_addresses(tenant: TenantContext, emails: Sequence[str]) -> set[str]:
    """Which of these addresses the firm's portal has locked now (lower-cased)."""
    async with tenant_session(tenant) as session:
        return await locked_emails(session, [e for e in emails if e])


async def grants_of_contacts(
    tenant: TenantContext, contact_ids: Sequence[UUID]
) -> list[ContactGrantRow]:
    async with tenant_session(tenant) as session:
        return await contact_grants(session, contact_ids)


async def invitations_of_contacts(
    tenant: TenantContext, contact_ids: Sequence[UUID]
) -> dict[UUID, dict[str, object]]:
    """Each contact's newest invitation."""
    async with tenant_session(tenant) as session:
        rows = await contact_invitations(session, contact_ids)
    newest: dict[UUID, dict[str, object]] = {}
    for row in rows:
        contact = cast(UUID, row["contact_id"])
        newest.setdefault(contact, dict(row))
    return newest


async def authorise_grants(
    ctx: AuthContext, client_id: UUID, grants: Sequence[ContactGrant]
) -> None:
    """The invitation's check before its idempotency lookup (ED-023's shape): every grant's
    scope is the client's and the caller may give it now."""
    _human(ctx, "client_access.grant")
    _valid(grants)
    await _authorise_each(
        ctx, "client_access.grant", await _resources(ctx.tenant, client_id, grants)
    )


async def invitation_contact(tenant: TenantContext, invitation_id: UUID) -> UUID | None:
    """The contact a contact invitation is for; None for any other invitation, or none."""
    async with tenant_session(tenant) as session:
        row = await get_invitation(session, invitation_id)
    if row is None or row["grant_ids"] is None:
        return None
    return cast(UUID | None, row["contact_id"])
