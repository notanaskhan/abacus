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
                    `notify` obligations are met by the action's own event (SPEC-013)
An agent is also bounded by its initiator, checked live (ADR-025): the initiator must be allowed
the same action, or `AGENT_ONLY_REACH` for actions no human role holds.
Matrix conditions not modelled yet (`in_scope`, `firm_setting(...)`, `assigned_only`,
`client_visible_only`, `task_scope`) are not grants: they deny until their task models them.

Ethical walls (ADR-026, SPEC-002) come before roles: a person walled off from a client is denied
every engagement of it, whatever their roles, and agents and system runs with them. The walled
clients are read once per request (`recording_checks`) and live on every step elsewhere.
Client access (`access_expired`) arrives with client users.

A successful `authorise` (and every `visible` filter built) is recorded for the request being
served, so a route that returns a success without one fails closed (`routing.AbacusRoute`). The
guard hides the response; it can't undo a write, so authorise before doing anything.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, false, select, true
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import Actor, AgentContext, AuthContext, SystemContext
from abacus.modules.identity.repository import (
    ENGAGEMENT_ROLES,
    engagement_members,
    engagement_role,
    ethical_walls,
    walled_clients,
)

MFA_RECENT = timedelta(minutes=15)
# Ethical walls (ADR-026; SPEC-002) are enforced below, before roles: the API may start in
# production (founder decision 2026-10-06: walls gate the first real firm).
WALL_SAFE = True
Layer = Literal["tenancy", "wall", "relationship", "role", "attribute", "delegation"]

EngagementColumn = ColumnElement[UUID] | QueryableAttribute[UUID]
# The engagements module tells identity how to find an engagement's client (TASK-016 Q1):
# identity owns walls, engagements owns the engagement-to-client fact, and identity never imports
# engagements. `column` turns an engagement-ID column into its client-ID subquery (for
# `visible()`); `lookup` finds one engagement's client (for `authorise`, when the resource
# doesn't carry it). Unregistered, walled people are denied everything engagement-scoped.
ClientColumn = Callable[[EngagementColumn], ColumnElement[UUID]]
ClientLookup = Callable[[TenantContext, UUID], Awaitable[UUID | None]]
_engagement_client: tuple[ClientColumn, ClientLookup] | None = None


def register_engagement_client(column: ClientColumn, lookup: ClientLookup) -> None:
    global _engagement_client
    if _engagement_client is not None and _engagement_client != (column, lookup):
        raise RuntimeError("the engagement-to-client lookup is already registered")
    _engagement_client = (column, lookup)


# An action no human role holds (agent and system only, e.g. `screening.run`) can't be intersected
# with the initiator's own right to it; the agent then stays within the initiator's reach: they
# must be allowed this action on the same engagement (founder decision 2026-10-06, ADR-025).
AGENT_ONLY_REACH = "evidence.read"
_NON_HUMAN_ROLES = frozenset({"agent", "system"})
_log = get_logger(__name__)
_checked: ContextVar[set[str] | None] = ContextVar("abacus_authz_checked", default=None)
# Each person's walled clients, read once per request (SPEC-002 §16); None outside a request.
_walls: ContextVar[dict[UUID, frozenset[UUID]] | None] = ContextVar(
    "abacus_authz_walls", default=None
)


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
    # The engagement's client, for the wall check (SPEC-002). Looked up when absent.
    client_id: UUID | None = None

    @classmethod
    def firm(cls, tenant_id: UUID) -> Resource:
        return cls(tenant_id, None, False)

    @classmethod
    def engagement(
        cls,
        tenant_id: UUID,
        engagement_id: UUID,
        *,
        archived: bool,
        client_id: UUID | None = None,
    ) -> Resource:
        return cls(tenant_id, engagement_id, archived, client_id)


@contextmanager
def recording_checks() -> Generator[set[str]]:
    """Collect the actions checked while serving one request."""
    checked: set[str] = set()
    token = _checked.set(checked)
    walls_token = _walls.set({})
    try:
        yield checked
    finally:
        _walls.reset(walls_token)
        _checked.reset(token)


def serving_request() -> bool:
    """Whether this code runs inside an API request being served (`AbacusRoute`). Workers, agents
    and scripts never are: a decision only a person may make refuses outside one (ADR-005)."""
    return _checked.get() is not None


def _record(action: str) -> None:
    checked = _checked.get()
    if checked is not None:
        checked.add(action)


def _rule(action: str) -> Rule:
    rule = RULES.get(action)
    if rule is None:
        raise UnknownAction(f"{action!r} is not in the permission matrix")
    return rule


def agent_may_hold(action: str) -> bool:
    """Whether an agent's task scope may declare this action (matrix `agent: task_scope`)."""
    return _rule(action).decisions.get("agent") == "task_scope"


def _human_held(rule: Rule) -> bool:
    return any(
        role not in _NON_HUMAN_ROLES and decision != "deny"
        for role, decision in rule.decisions.items()
    )


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
    # 2a. Ethical walls, before any role (ADR-026): the person acting (a user, the person a
    # system run or agent acts for) must not be walled off from the engagement's client.
    if await _walled(ctx, resource):
        raise _deny(ctx, action, "wall")
    # 2b. Relationships.
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
        delegated = action if _human_held(rule) else AGENT_ONLY_REACH
        try:
            await authorise(ctx.initiator, delegated, resource, reason=reason)
        except Forbidden as denied:
            # An attribute the initiator fails (an archived engagement) is the agent's too.
            layer: Layer = "attribute" if denied.layer == "attribute" else "delegation"
            raise _deny(ctx, action, layer) from None
    # 4. Attributes.
    if resource.archived and not rule.reads:
        raise _deny(ctx, action, "attribute")
    mfa_at = ctx.mfa_at if isinstance(ctx, AuthContext) else None
    if rule.mfa_recent and (mfa_at is None or datetime.now(UTC) - mfa_at > MFA_RECENT):
        raise _deny(ctx, action, "attribute")
    if rule.requires_reason and not (reason and reason.strip()):
        raise _deny(ctx, action, "attribute")
    # `notify` (SPEC-013): a person's action is allowed, and its service emits the event its
    # catalogue entry notifies on, in the same unit of work (today only `engagement.self_join`).
    # Agents and the platform never carry the obligation.
    if rule.notify and not isinstance(ctx, AuthContext):
        raise _deny(ctx, action, "attribute")
    _record(action)
    _log.info("authz.allowed", action=action, tenant_id=ctx.tenant_id, **_who(ctx))


def _person(ctx: Actor) -> UUID:
    """Who is acting, for walls: the user, or the person a system run or agent acts for."""
    if isinstance(ctx, AuthContext):
        return ctx.user_id
    if isinstance(ctx, AgentContext):
        return ctx.initiator.user_id
    return ctx.on_behalf_of


async def _walled(ctx: Actor, resource: Resource) -> bool:
    if resource.engagement_id is None:
        return False  # walls are on clients' engagements; firm-level actions aren't walled
    person = _person(ctx)
    cache = _walls.get()
    walls = cache.get(person) if cache is not None else None
    if walls is None:
        walls = await walled_clients(ctx.tenant, person)
        if cache is not None:
            cache[person] = walls
    if not walls:
        return False
    client = resource.client_id
    if client is None:
        if _engagement_client is None:
            return True  # can't tell which client: a walled person is denied (fail closed)
        client = await _engagement_client[1](ctx.tenant, resource.engagement_id)
    return client is None or client in walls


def _not_walled(ctx: Actor, engagement_id: EngagementColumn) -> ColumnElement[bool]:
    """Rows whose engagement's client the acting person isn't walled off from (ADR-026)."""
    walls = select(ethical_walls.c.id).where(
        ethical_walls.c.tenant_id == ctx.tenant_id,
        ethical_walls.c.user_id == _person(ctx),
        ethical_walls.c.status == "active",
    )
    if _engagement_client is not None:
        walls = walls.where(ethical_walls.c.client_id == _engagement_client[0](engagement_id))
    return ~walls.correlate_except(ethical_walls).exists()


def visible(ctx: Actor, action: str, engagement_id: EngagementColumn) -> ColumnElement[bool]:
    """A filter for list queries: rows whose engagement the actor may `action` (a read action),
    minus walled clients. Agrees with `authorise` for every role. Apply it: building it counts as
    the route's check."""
    by_role = _visible_by_role(ctx, action, engagement_id)
    if isinstance(ctx, AgentContext):
        return by_role  # the initiator's filter, inside, already excludes their walls
    return and_(by_role, _not_walled(ctx, engagement_id))


def _visible_by_role(
    ctx: Actor, action: str, engagement_id: EngagementColumn
) -> ColumnElement[bool]:
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
    "register_engagement_client",
    "serving_request",
    "visible",
]
