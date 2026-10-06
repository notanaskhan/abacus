"""`authorise` and `visible`: the only permission logic in the product (ADR-020, ADR-023, ADR-027).
PROTECTED. TASK-007 design §5.

    await authorise(ctx, "request_item.create", Resource(ctx.tenant_id, engagement_id=eng.id))
    q = select(Engagement).where(visible(ctx, "engagement.read_metadata", Engagement.id))

`authorise` evaluates four layers in order; any layer denying means deny, and deny is the default:
  1. tenancy        the resource belongs to the active tenant
  2. relationships  the roles the actor holds here: firm role, plus engagement role on the
                    resource's engagement (no relationship at all: deny)
  3. roles          the matrix decision for those roles; an explicit `deny` beats any `allow`
  4. attributes     archived engagements are read-only; `mfa_recent`; `requires: reason`;
                    actions carrying an obligation not built yet (`notify`) deny
Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`,
`client_visible_only`, `task_scope`) are not grants: they deny until their task models them.

NOT WALL-SAFE YET: ethical walls (ADR-026) are not modelled, so `walled: deny` is never applied.
No route serving engagement data may ship to a firm before walls exist (TASK-007 decision log).
Client access (`access_expired`) arrives with client users.

A successful `authorise` (and every `visible` filter built) is recorded for the request being
served, so a route that returns a success without one fails closed (`routing.AbacusRoute`). The
guard hides the response; it can't undo a write, so authorise before doing anything.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, false, select, true
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.logging import get_logger
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import Actor, AgentContext, AuthContext, SystemContext
from abacus.modules.identity.repository import (
    ENGAGEMENT_ROLES,
    engagement_members,
    engagement_role,
)

MFA_RECENT = timedelta(minutes=15)
# Ethical walls (ADR-026) are not modelled yet. The API refuses to start in production until they
# are (founder decision 2026-10-06: walls gate the first real firm). Set True only with walls.
WALL_SAFE = False
Layer = Literal["tenancy", "relationship", "role", "attribute", "delegation"]
_log = get_logger(__name__)
_checked: ContextVar[set[str] | None] = ContextVar("abacus_authz_checked", default=None)


class Forbidden(Exception):
    """Access denied. `layer` says which layer denied (logged; never shown to the caller)."""

    def __init__(self, action: str, layer: Layer) -> None:
        super().__init__(f"{action} denied at {layer}")
        self.action = action
        self.layer = layer


class UnknownAction(ValueError):
    """An action that isn't in the permission matrix: a programming error, never a grant."""


@dataclass(frozen=True)
class Resource:
    """What an action is done to. Build it with `firm` or `engagement`: an engagement resource
    must state whether the engagement is archived (TASK-008 loads that from the database)."""

    tenant_id: UUID
    engagement_id: UUID | None
    archived: bool

    @classmethod
    def firm(cls, tenant_id: UUID) -> Resource:
        return cls(tenant_id, None, False)

    @classmethod
    def engagement(cls, tenant_id: UUID, engagement_id: UUID, *, archived: bool) -> Resource:
        return cls(tenant_id, engagement_id, archived)


@contextmanager
def recording_checks() -> Generator[set[str]]:
    """Collect the actions checked while serving one request."""
    checked: set[str] = set()
    token = _checked.set(checked)
    try:
        yield checked
    finally:
        _checked.reset(token)


def _record(action: str) -> None:
    checked = _checked.get()
    if checked is not None:
        checked.add(action)


def _rule(action: str) -> Rule:
    rule = RULES.get(action)
    if rule is None:
        raise UnknownAction(f"{action!r} is not in the permission matrix")
    return rule


def _who(ctx: Actor) -> dict[str, object]:
    if isinstance(ctx, AuthContext):
        return {"user_id": ctx.user_id}
    if isinstance(ctx, AgentContext):
        return {
            "agent_id": ctx.agent_id,
            "agent_run_id": ctx.agent_run_id,
            "on_behalf_of": ctx.initiator.user_id,
        }
    return {"system_run_id": ctx.run_id, "on_behalf_of": ctx.on_behalf_of}


def _deny(ctx: Actor, action: str, layer: Layer) -> Forbidden:
    _log.info("authz.denied", action=action, layer=layer, tenant_id=ctx.tenant_id, **_who(ctx))
    return Forbidden(action, layer)


async def _roles(ctx: Actor, resource: Resource) -> set[str]:
    if isinstance(ctx, AgentContext):
        return {"agent"} if resource.engagement_id == ctx.engagement_id else set()
    if isinstance(ctx, SystemContext):
        # The platform acts on its run's engagement only: anything else (another engagement, a
        # firm-level action) has no relationship.
        return {"system"} if resource.engagement_id == ctx.engagement_id else set()
    roles: set[str] = set()
    if ctx.firm_role is not None:
        roles.add(ctx.firm_role)
    if resource.engagement_id is not None:
        role = await engagement_role(ctx.tenant, ctx.user_id, resource.engagement_id)
        if role is not None:
            roles.add(role)
    return roles


async def authorise(
    ctx: Actor, action: str, resource: Resource, *, reason: str | None = None
) -> None:
    """Return if allowed; raise `Forbidden` otherwise."""
    rule = _rule(action)
    # 1. Tenancy.
    if resource.tenant_id != ctx.tenant_id:
        raise _deny(ctx, action, "tenancy")
    # 2. Relationships.
    roles = await _roles(ctx, resource)
    if not roles:
        raise _deny(ctx, action, "relationship")
    # 3. Roles. For an agent, `task_scope` grants only what its run declared (ADR-025).
    decisions = {rule.decisions.get(role) for role in roles}
    if isinstance(ctx, AgentContext) and "task_scope" in decisions and action in ctx.task_scope:
        decisions = (decisions - {"task_scope"}) | {"allow"}
    if "deny" in decisions or "allow" not in decisions:
        raise _deny(ctx, action, "role")
    # An agent never exceeds the person it acts for (ADR-025 intersection), checked live.
    if isinstance(ctx, AgentContext):
        try:
            await authorise(ctx.initiator, action, resource, reason=reason)
        except Forbidden:
            raise _deny(ctx, action, "delegation") from None
    # 4. Attributes.
    if resource.archived and not rule.reads:
        raise _deny(ctx, action, "attribute")
    mfa_at = ctx.mfa_at if isinstance(ctx, AuthContext) else None
    if rule.mfa_recent and (mfa_at is None or datetime.now(UTC) - mfa_at > MFA_RECENT):
        raise _deny(ctx, action, "attribute")
    if rule.requires_reason and not (reason and reason.strip()):
        raise _deny(ctx, action, "attribute")
    if rule.notify:
        raise _deny(ctx, action, "attribute")
    _record(action)
    _log.info("authz.allowed", action=action, tenant_id=ctx.tenant_id, **_who(ctx))


def visible(
    ctx: Actor, action: str, engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID]
) -> ColumnElement[bool]:
    """A filter for list queries: rows whose engagement the actor may `action` (a read action).
    Agrees with `authorise` for every role. Apply it: building it counts as the route's check."""
    rule = _rule(action)
    if not rule.reads:
        raise ValueError(f"visible() filters reads; {action!r} is not a read action")
    if rule.mfa_recent or rule.requires_reason or rule.notify:
        raise ValueError(f"visible() can't apply {action!r}'s conditions; use authorise()")
    _record(action)
    if isinstance(ctx, AgentContext):
        agent = rule.decisions.get("agent")
        if not (agent == "allow" or (agent == "task_scope" and action in ctx.task_scope)):
            return false()
        return and_(
            engagement_id == ctx.engagement_id, visible(ctx.initiator, action, engagement_id)
        )
    if isinstance(ctx, SystemContext):
        if rule.decisions.get("system") != "allow":
            return false()
        return engagement_id == ctx.engagement_id
    firm = rule.decisions.get(ctx.firm_role) if ctx.firm_role is not None else None
    if firm == "allow":
        return true()
    if firm == "deny":
        return false()
    roles = [
        role
        for role, decision in rule.decisions.items()
        if decision == "allow" and role in ENGAGEMENT_ROLES
    ]
    if not roles:
        return false()
    member_of = select(engagement_members.c.engagement_id).where(
        engagement_members.c.tenant_id == ctx.tenant_id,
        engagement_members.c.user_id == ctx.user_id,
        engagement_members.c.role.in_(roles),
    )
    return engagement_id.in_(member_of)


__all__ = [
    "MFA_RECENT",
    "WALL_SAFE",
    "Forbidden",
    "Resource",
    "UnknownAction",
    "authorise",
    "recording_checks",
    "visible",
]
