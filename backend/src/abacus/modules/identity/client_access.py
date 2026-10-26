"""Client access grants, the role-union portal shell and `scope_only` (F-03-T26; ADR-146, P-09;
chapter 03 §4.2; DEC-34, DEC-129). PROTECTED.

A grant gives one client user one role on one scope: `client`, `client_entity`, `engagement`,
`work_item`, `request_item`, `k1_package`, `governance_room`, `component` or `intake`. Owners
register how to resolve their scope kinds (`slots.register_scope_resolver`); `engagement` is
built in. An unregistered kind covers nothing (fail closed).

- `portal_scopes(ctx)`: the union of the person's active grants. The shell is "full" when any
  grant has a full-client role, "k1" when every grant is a K-1 recipient's ("My K-1s"),
  "limited" for third parties, TCWG, prospects and component auditors, and "none" without
  grants (DEC-129).
- `scope_covers`: the `scope_only` condition's facts. A request is judged against the grant for
  the target's own scope only: a grant covers an engagement's target when it names that
  engagement, that work item, or (with no engagement of its own) the engagement's client.
- `grant_client_access` / `revoke_client_access`: through `authorise` (`client_access.grant`,
  `.revoke`), an audit event, an insert-only `client_access_events` row and the
  `client_access.*` and `access.changed` events.

The matrix keeps two client role names: an engagement-scope `owner` grant is `client_admin`, a
`contributor` grant `client_contributor` (`repository.MATRIX_ROLE_OF`). `engagement_members`
holds staff roles only (migration 0084, TASK-373).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, get_args
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.identity.authz import Resource, authorise, engagement_client
from abacus.modules.identity.authz.conditions import register_client_scope, register_third_party
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.events import AccessChanged, ClientAccessGranted, ClientAccessRevoked
from abacus.modules.identity.repository import (
    GrantRow,
    active_grants,
    active_memberships,
    delegate_grant_holders,
    delegate_holders,
    engagement_members_of,
    get_grant,
    insert_grant,
    insert_grant_event,
    set_grant_status,
)
from abacus.modules.identity.slots import ScopeFacts, resolve_scope, resolve_scopes

GrantRole = Literal[
    "owner",
    "contributor",
    "plan_administrator",
    "trustee",
    "taxpayer",
    "spouse",
    "delegate",
    "third_party",
    "k1_recipient",
    "tcwg",
    "prospect",
    "component_auditor",
]
ScopeKind = Literal[
    "client",
    "client_entity",
    "engagement",
    "work_item",
    "request_item",
    "k1_package",
    "governance_room",
    "component",
    "intake",
]
Shell = Literal["full", "k1", "limited", "none"]
GRANT_ROLES: Final = frozenset(get_args(GrantRole))
SCOPE_KINDS: Final = frozenset(get_args(ScopeKind))
# The roles that open the full client shell (DEC-129); the rest see only their scopes.
FULL_ROLES: Final = frozenset(
    {"owner", "contributor", "plan_administrator", "trustee", "taxpayer", "spouse", "delegate"}
)
# Client-wide scopes: granted on the firm, by a firm administrator, never by one engagement.
_CLIENT_WIDE: Final = frozenset({"client", "client_entity"})


class GrantScopeInvalid(DomainInvalid):
    """The scope can't be resolved, or isn't the engagement's (or the firm's) to grant."""

    code = "grant_scope_invalid"


class GrantExists(DomainConflict):
    """The person already holds this role on this scope."""

    code = "grant_exists"


@dataclass(frozen=True)
class GrantScope:
    role: str
    scope_kind: str
    scope_id: UUID
    document_classes: tuple[str, ...] | None


@dataclass(frozen=True)
class PortalScopes:
    shell: Shell
    scopes: tuple[GrantScope, ...]


def shell_of(roles: Iterable[str]) -> Shell:
    """The role-union shell for a person's active grant roles (DEC-129)."""
    held = set(roles)
    if not held:
        return "none"
    if held & FULL_ROLES:
        return "full"
    if held == {"k1_recipient"}:
        return "k1"
    return "limited"


def _scope(grant: GrantRow) -> GrantScope:
    return GrantScope(grant.role, grant.scope_kind, grant.scope_id, grant.document_classes)


async def portal_scopes(ctx: AuthContext) -> PortalScopes:
    """The person's role union in the active firm: the shell, and every scope a grant covers."""
    grants = await active_grants(ctx.tenant, ctx.user_id)
    return PortalScopes(shell_of(g.role for g in grants), tuple(_scope(g) for g in grants))


async def scope_facts(tenant: TenantContext, kind: str, scope_id: UUID) -> ScopeFacts | None:
    """What a grant's scope covers (its client, and its engagement or work item if narrower), or
    None for an unknown scope: the portal home composes one scope (P-08-T13)."""
    if kind == "engagement":
        client = await engagement_client(tenant, scope_id)
        return None if client is None else ScopeFacts(client, engagement_id=scope_id)
    return await resolve_scope(tenant, kind, scope_id)


def _covers(
    facts: ScopeFacts, engagement_id: UUID, work_item_id: UUID | None, client_id: UUID | None
) -> bool:
    if facts.work_item_id is not None:
        return facts.work_item_id == work_item_id
    if facts.engagement_id is not None:
        return facts.engagement_id == engagement_id
    return client_id is not None and facts.client_id == client_id


async def scope_covers(
    tenant: TenantContext, user_id: UUID, engagement_id: UUID, work_item_id: UUID | None
) -> bool:
    """Whether one of the person's grants covers the target (`scope_only`)."""
    grants = await active_grants(tenant, user_id)
    if not grants:
        return False
    client_id = await engagement_client(tenant, engagement_id)
    for grant in grants:
        facts = await scope_facts(tenant, grant.scope_kind, grant.scope_id)
        if facts is not None and _covers(facts, engagement_id, work_item_id, client_id):
            return True
    return False


register_client_scope(scope_covers)

# R-01-T13 (DEC-387): the grant roles a request's delegation issues: CLI-04's `third_party`
# (P-07-T25) and P-06's `delegate`. On a `request_item` scope either makes its holder the
# matrix's `third_party` on that request's engagement, reaching only what is delegated to them.
DELEGATE_ROLES: Final = frozenset({"third_party", "delegate"})


async def third_party_on(tenant: TenantContext, user_id: UUID, engagement_id: UUID) -> bool:
    """Whether the person holds an active, unexpired delegate's grant on a request of the
    engagement (the scopes resolved by the owner of `request_item` in one call; unresolved, no).
    Read only for a client person with no role on the engagement: a client role wins (DEC-390)."""
    items = [
        g.scope_id
        for g in await active_grants(tenant, user_id)
        if g.role in DELEGATE_ROLES and g.scope_kind == "request_item"
    ]
    if not items:
        return False
    found = await resolve_scopes(tenant, "request_item", items)
    return any(f.engagement_id == engagement_id for f in found.values())


register_third_party(third_party_on)


async def may_receive_about(tenant: TenantContext, user_id: UUID, engagement_id: UUID) -> bool:
    """R-01-T19 security review H: whether a firm email about this engagement may go to this
    person. They must hold an active membership in the firm and either be on the engagement's
    team or hold an active grant whose scope covers the engagement (its client, entity, the
    engagement itself, one of its work items or a request delegated to them). Read under the
    firm's row-level security, so another firm's people never qualify."""
    if not any(m.tenant_id == tenant.tenant_id for m in await active_memberships(user_id)):
        return False
    if any(member == user_id for member, _ in await engagement_members_of(tenant, engagement_id)):
        return True
    client_id = await engagement_client(tenant, engagement_id)
    for grant in await active_grants(tenant, user_id):
        facts = await scope_facts(tenant, grant.scope_kind, grant.scope_id)
        if facts is None:
            continue
        if facts.engagement_id is not None:
            if facts.engagement_id == engagement_id:
                return True
        elif facts.work_item_id is None and client_id is not None and facts.client_id == client_id:
            return True
    return await third_party_on(tenant, user_id, engagement_id)


async def delegation_holders_by_grant(
    tenant: TenantContext, grants: Sequence[tuple[UUID, UUID]]
) -> dict[UUID, UUID]:
    """Many (request item, grant) pairs at once (the room, security review L2): each grant whose
    holder `delegated_only` would name, -> that holder; only an active delegate grant on that
    very request counts."""
    held = await delegate_grant_holders(tenant, [g for _, g in grants])
    out: dict[UUID, UUID] = {}
    for item_id, grant_id in grants:
        found = held.get(grant_id)
        if found is not None and found[1] == item_id:
            out[grant_id] = found[0]
    return out


async def delegation_holders(
    tenant: TenantContext, item_id: UUID, grant_ids: Sequence[UUID]
) -> frozenset[UUID]:
    """The people `delegated_only` lets act on the request: of these grants (the request's open
    delegations', read by requests), the holders of active, unexpired delegate grants on this
    very request. A pending grant (its invitation not accepted yet) has nobody."""
    return await delegate_holders(tenant, item_id, grant_ids)


def _resource_matches(resource: Resource, kind: str, facts: ScopeFacts | None) -> bool:
    if facts is None:
        return False
    if kind in _CLIENT_WIDE:
        return resource.engagement_id is None
    return facts.engagement_id is not None and facts.engagement_id == resource.engagement_id


async def grant_client_access(
    ctx: AuthContext,
    resource: Resource,
    *,
    user_id: UUID,
    role: GrantRole,
    scope_kind: ScopeKind,
    scope_id: UUID,
    contact_id: UUID | None = None,
    document_classes: Sequence[str] | None = None,
    expires_at: datetime | None = None,
    action: Literal["client_access.grant", "request_item.delegate"] = "client_access.grant",
) -> UUID:
    """Grant a client user a role on a scope. `resource` is the scope's engagement (built from
    its row by the caller), or the firm for client-wide scopes. Returns the grant's id. A
    request's delegation (P-06-T10) is checked as `request_item.delegate` and only ever grants
    the `delegate` role on that one `request_item`."""
    if role not in GRANT_ROLES or scope_kind not in SCOPE_KINDS:
        raise GrantScopeInvalid
    if action == "request_item.delegate" and (role, scope_kind) != ("delegate", "request_item"):
        raise GrantScopeInvalid
    await authorise(ctx, action, resource)
    if not _resource_matches(
        resource, scope_kind, await scope_facts(ctx.tenant, scope_kind, scope_id)
    ):
        raise GrantScopeInvalid
    async with uow(ctx.tenant) as tx:
        grant_id = await grant_in_unit_of_work(
            tx,
            tenant_id=ctx.tenant_id,
            target=_target(resource),
            user_id=user_id,
            role=role,
            scope_kind=scope_kind,
            scope_id=scope_id,
            granted_by=ctx.user_id,
            contact_id=contact_id,
            document_classes=document_classes,
            expires_at=expires_at,
        )
        if grant_id is None:
            raise GrantExists
        tx.emit(AccessChanged(user_id=user_id))
    return grant_id


async def grant_in_unit_of_work(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    target: Target,
    user_id: UUID,
    role: GrantRole,
    scope_kind: ScopeKind,
    scope_id: UUID,
    granted_by: UUID,
    contact_id: UUID | None = None,
    document_classes: Sequence[str] | None = None,
    expires_at: datetime | None = None,
) -> UUID | None:
    """The one way a grant is written, inside the caller's unit of work: the grant, its
    `client_access_events` row and the `client_access.granted` audit event and outbox event,
    all `by` `granted_by`. None when the person already holds that role on that scope.
    `grant_client_access` authorises first; an invitation's acceptance (P-08-T18) writes the
    template the inviter was authorised to issue, attributed to the inviter. The caller emits
    `access.changed` (acceptance ends the person's other sessions itself, DEC-275)."""
    if role not in GRANT_ROLES or scope_kind not in SCOPE_KINDS:
        raise GrantScopeInvalid
    grant_id = await insert_grant(
        tx.session,
        {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "contact_id": contact_id,
            "role": role,
            "scope_kind": scope_kind,
            "scope_id": scope_id,
            "document_classes": list(document_classes) if document_classes else None,
            "granted_by": granted_by,
            "expires_at": expires_at,
        },
    )
    if grant_id is None:
        return None
    await insert_grant_event(
        tx.session, tenant_id=tenant_id, grant_id=grant_id, event="granted", by=granted_by
    )
    tx.record("client_access.granted", target=target)
    tx.emit(ClientAccessGranted(grant_id=grant_id, user_id=user_id))
    return grant_id


async def revoke_client_access(ctx: AuthContext, resource: Resource, grant_id: UUID) -> bool:
    """Revoke a grant on `resource`'s scope (as for granting). Whether it was active."""
    async with tenant_session(ctx.tenant) as session:
        grant = await get_grant(session, grant_id)
    if grant is None:
        raise NotFound("client_access_grant")
    await authorise(ctx, "client_access.revoke", resource)
    facts = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
    if not _resource_matches(resource, grant.scope_kind, facts):
        raise NotFound("client_access_grant")
    async with uow(ctx.tenant) as tx:
        revoked = await set_grant_status(tx.session, grant_id, "revoked")
        if revoked:
            await insert_grant_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                grant_id=grant_id,
                event="revoked",
                by=ctx.user_id,
            )
            tx.emit(ClientAccessRevoked(grant_id=grant_id, user_id=grant.user_id))
            tx.emit(AccessChanged(user_id=grant.user_id))
        tx.record("client_access.revoked", target=_target(resource))
    return revoked


def _target(resource: Resource) -> Target:
    if resource.engagement_id is not None:
        return Target("engagement", resource.engagement_id)
    return Target("firm", resource.tenant_id)
