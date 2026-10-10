"""`authorise` and `visible`: the only permission logic in the product (ADR-020, ADR-023, ADR-027).
PROTECTED. TASK-007 design §5.

    await authorise(ctx, "request_item.create", Resource(ctx.tenant_id, engagement_id=eng.id))
    q = select(Engagement).where(visible(ctx, "engagement.read_metadata", Engagement.id))

`authorise` evaluates four layers in order; any layer denying means deny, and deny is the default:
  1. tenancy        the resource belongs to the active tenant
  2. relationships  the roles the actor holds here: firm role, plus engagement role on the
                    resource's engagement (no relationship at all: deny)
  3. roles          the matrix decision for those roles; an explicit `deny` beats any `allow`
  3b. independence for an action marked `independence: required` (SPEC-025 AC-7), a staff
                    engagement role grants it only once that person has confirmed their
                    independence for the engagement (firm and client roles, support and system
                    runs aren't bound; agents are, through their initiator)
  4. attributes     archived engagements are read-only; `mfa_recent`; `requires: reason`;
                    `notify` obligations are met by the action's own event (SPEC-013)
An agent is also bounded by its initiator, checked live (ADR-025): the initiator must be allowed
the same action, or `AGENT_ONLY_REACH` for actions no human role holds.
Matrix conditions not modelled yet (`in_scope`, other `firm_setting(...)`s, `task_scope` for
humans) are not grants: they deny until their task models them. `firm_setting(autonomy_policy)`
is modelled for agents only (SPEC-027, TASK-051): allowed at the firm's Routine autonomy or
higher, within the agent's scope (an agent's only firm setting in the matrix). The client
conditions (SPEC-020, TASK-035 D2) need the item's facts on the resource (`ItemFacts`):
`client_visible_only` allows a client-visible item, `assigned_only` a client-visible item
assigned to the person. Without the facts they deny. `visible_items` is their list-query twin.

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

from sqlalchemy import ColumnElement, Select, and_, false, or_, select, true
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import Actor, AgentContext, AuthContext, SystemContext
from abacus.modules.identity.repository import (
    CLIENT_ROLES,
    ENGAGEMENT_ROLES,
    engagement_members,
    engagement_role,
    engagement_roles_in_firm,
    ethical_walls,
    walled_clients,
)

MFA_RECENT = timedelta(minutes=15)
# Ethical walls (ADR-026; SPEC-002) are enforced below, before roles: the API may start in
# production (founder decision 2026-10-06: walls gate the first real firm).
WALL_SAFE = True
Layer = Literal[
    "tenancy", "wall", "relationship", "role", "independence", "attribute", "delegation"
]

EngagementColumn = ColumnElement[UUID] | QueryableAttribute[UUID]
BoolColumn = ColumnElement[bool] | QueryableAttribute[bool]
UserColumn = ColumnElement[UUID] | ColumnElement[UUID | None] | QueryableAttribute[UUID | None]
_CLIENT_CONDITIONS = frozenset({"client_visible_only", "assigned_only"})
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


# SPEC-025 (TASK-045 D2): whether a person has confirmed their independence for an engagement,
# registered by the engagements module (which owns the confirmations). `column` turns an
# engagement-ID column and a user into an EXISTS (for `visible()`); `lookup` answers for one
# engagement (for `authorise`). Unregistered, a staff engagement role never grants an action
# marked `independence: required` (fail closed).
IndependenceColumn = Callable[[EngagementColumn, UUID], ColumnElement[bool]]
IndependenceLookup = Callable[[TenantContext, UUID, UUID], Awaitable[bool]]
_independence: tuple[IndependenceColumn, IndependenceLookup] | None = None


def register_independence(column: IndependenceColumn, lookup: IndependenceLookup) -> None:
    global _independence
    if _independence is not None and _independence != (column, lookup):
        raise RuntimeError("the independence lookup is already registered")
    _independence = (column, lookup)


# SPEC-014 (ADR-106): the firm's non-archived engagements, registered by the engagements module;
# without it, engagement roles never count at firm level (fail closed).
ActiveEngagements = Callable[[], Select[UUID]]
_active_engagements: ActiveEngagements | None = None


def register_active_engagements(active: ActiveEngagements) -> None:
    global _active_engagements
    if _active_engagements is not None and _active_engagements is not active:
        raise RuntimeError("the active-engagement subquery is already registered")
    _active_engagements = active


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
# Each person's confirmed engagements, answered once per request (SPEC-025).
_confirmed: ContextVar[dict[tuple[UUID, UUID], bool] | None] = ContextVar(
    "abacus_authz_confirmed", default=None
)
# Each person's engagement roles in the firm, read once per request (SPEC-014).
_firm_engagement_roles: ContextVar[dict[UUID, frozenset[str]] | None] = ContextVar(
    "abacus_authz_firm_engagement_roles", default=None
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
class ItemFacts:
    """A request item's client facts, for the client conditions (SPEC-020; TASK-035 D2)."""

    client_visible: bool
    client_assignee: UUID | None


@dataclass(frozen=True)
class Resource:
    """What an action is done to. Build it with `firm` or `engagement`: an engagement resource
    must state whether the engagement is archived (TASK-008 loads that from the database)."""

    tenant_id: UUID
    engagement_id: UUID | None
    archived: bool
    # The engagement's client, for the wall check (SPEC-002). Looked up when absent.
    client_id: UUID | None = None
    # The request item acted on, for `client_visible_only` and `assigned_only`.
    item: ItemFacts | None = None

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
        item: ItemFacts | None = None,
    ) -> Resource:
        return cls(tenant_id, engagement_id, archived, client_id, item)


@contextmanager
def recording_checks() -> Generator[set[str]]:
    """Collect the actions checked while serving one request."""
    checked: set[str] = set()
    token = _checked.set(checked)
    walls_token = _walls.set({})
    confirmed_token = _confirmed.set({})
    roles_token = _firm_engagement_roles.set({})
    try:
        yield checked
    finally:
        _firm_engagement_roles.reset(roles_token)
        _confirmed.reset(confirmed_token)
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


def policy_agent_may_hold(action: str) -> bool:
    """SPEC-027 (TASK-051): a deterministic agent (no model call) may also declare routine
    actions the firm's autonomy policy allows (`agent: firm_setting(autonomy_policy)`)."""
    return agent_may_hold(action) or _rule(action).decisions.get("agent") == AUTONOMY_POLICY


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


async def _engagement_roles_in_firm(ctx: AuthContext) -> frozenset[str]:
    if _active_engagements is None:
        return frozenset()
    cache = _firm_engagement_roles.get()
    found = cache.get(ctx.user_id) if cache is not None else None
    if found is None:
        try:
            found = await engagement_roles_in_firm(ctx.tenant, ctx.user_id, _active_engagements())
        except Exception as exc:  # fail closed: no engagement roles (SPEC-014 §12)
            _log.warning("authz.firm_roles_unavailable", error=type(exc).__name__)
            return frozenset()
        if cache is not None:
            cache[ctx.user_id] = found
    return found


async def _roles(ctx: Actor, resource: Resource, rule: Rule) -> set[str]:
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
    elif (
        rule.reads
        and not ctx.is_support
        and (ctx.firm_role is None or rule.decisions.get(ctx.firm_role) != "allow")
    ):
        # SPEC-014: a firm-level read counts the person's engagement roles on the firm's active
        # engagements; skipped when the firm role already allows it (TASK-029 D2).
        roles |= await _engagement_roles_in_firm(ctx)
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
    roles = await _roles(ctx, resource, rule)
    if not roles:
        raise _deny(ctx, action, "relationship")
    # 3. Roles. For an agent, `task_scope` grants only what its run declared (ADR-025).
    by_role = {role: _on_item(rule.decisions.get(role), ctx, resource) for role in roles}
    decisions = set(by_role.values())
    if isinstance(ctx, AgentContext) and "task_scope" in decisions and action in ctx.task_scope:
        decisions = (decisions - {"task_scope"}) | {"allow"}
    # SPEC-027 (TASK-051 D2): an agent's routine action allowed by the firm's autonomy policy
    # (`follow_up.send`): Routine (level 1) or higher, read fresh; denied at Advise. Only in the
    # agent's declared scope, and the initiator intersection below still applies.
    if (
        isinstance(ctx, AgentContext)
        and AUTONOMY_POLICY in decisions
        and action in ctx.task_scope
        and await _autonomy_allows(ctx)
    ):
        decisions = (decisions - {AUTONOMY_POLICY}) | {"allow"}
    if "deny" in decisions or "allow" not in decisions:
        raise _deny(ctx, action, "role")
    # 3b. Independence (SPEC-025 AC-7, per person): when only a staff engagement role grants a
    # client-data action, it counts once that person has confirmed for this engagement. Firm and
    # client roles, break-glass support and system runs aren't bound by it; an agent is, through
    # its initiator below. A firm-level read (no engagement) lists rows that `visible()` filters
    # by the same rule, engagement by engagement.
    granting = {role for role, decision in by_role.items() if decision == "allow"}
    if (
        rule.independence
        and resource.engagement_id is not None
        and isinstance(ctx, AuthContext)
        and not ctx.is_support
        and granting <= ENGAGEMENT_ROLES
        and not await _confirmed_for(ctx, resource)
    ):
        raise _deny(ctx, action, "independence")
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


# The parsed matrix keeps a condition's kind, not its setting's name. The only agent
# `firm_setting(...)` in the matrix is `autonomy_policy` (`follow_up.send`); a test reading the
# YAML fails if another appears.
AUTONOMY_POLICY = "firm_setting"


async def _autonomy_allows(ctx: AgentContext) -> bool:
    from abacus.modules.identity.firm_settings import (  # firm_settings imports authz
        autonomy_level,
    )

    return await autonomy_level(ctx.tenant_id) >= 1


def _on_item(decision: str | None, ctx: Actor, resource: Resource) -> str | None:
    """A client condition met by the item's facts is an allow; unmet, it grants nothing."""
    if decision not in _CLIENT_CONDITIONS:
        return decision
    item = resource.item
    if item is None or not item.client_visible or not isinstance(ctx, AuthContext):
        return None
    if decision == "assigned_only" and item.client_assignee != ctx.user_id:
        return None
    return "allow"


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


async def _confirmed_for(ctx: AuthContext, resource: Resource) -> bool:
    if resource.engagement_id is None or _independence is None:
        return False  # unregistered: fail closed
    key = (ctx.user_id, resource.engagement_id)
    cache = _confirmed.get()
    if cache is not None and key in cache:
        return cache[key]
    confirmed = await _independence[1](ctx.tenant, resource.engagement_id, ctx.user_id)
    if cache is not None:
        cache[key] = confirmed
    return confirmed


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
    allowed = [role for role, decision in rule.decisions.items() if decision == "allow"]
    staff = [role for role in allowed if role in ENGAGEMENT_ROLES]
    client = [role for role in allowed if role in CLIENT_ROLES]
    if rule.independence and not ctx.is_support:
        # SPEC-025 (TASK-045): a staff engagement role counts once the person has confirmed.
        reach = [_member_of(ctx, engagement_id, client)] if client else []
        if staff and _independence is not None:
            confirmed = _independence[0](engagement_id, ctx.user_id)
            reach.append(and_(_member_of(ctx, engagement_id, staff), confirmed))
        return or_(*reach) if reach else false()
    if not staff and not client:
        return false()
    return _member_of(ctx, engagement_id, staff + client)


def _member_of(
    ctx: AuthContext, engagement_id: EngagementColumn, roles: list[str]
) -> ColumnElement[bool]:
    member_of = select(engagement_members.c.engagement_id).where(
        engagement_members.c.tenant_id == ctx.tenant_id,
        engagement_members.c.user_id == ctx.user_id,
        engagement_members.c.role.in_(roles),
    )
    return engagement_id.in_(member_of)


async def authorise_items(ctx: Actor, action: str, resource: Resource) -> None:
    """For a list of an engagement's request items (a read): allowed outright, or by a client
    condition, in which case `visible_items` then filters the rows (SPEC-020; TASK-035 D2)."""
    rule = _rule(action)
    if not rule.reads:
        raise ValueError(f"authorise_items() is for reads; {action!r} is not one")
    try:
        await authorise(ctx, action, resource)
    except Forbidden as denied:
        if denied.layer != "role" or not isinstance(ctx, AuthContext):
            raise
        roles = await _roles(ctx, resource, rule)
        if not any(rule.decisions.get(role) in _CLIENT_CONDITIONS for role in roles):
            raise
        _record(action)


def visible_items(
    ctx: Actor,
    action: str,
    engagement_id: EngagementColumn,
    client_visible: BoolColumn,
    client_assignee: UserColumn,
) -> ColumnElement[bool]:
    """`visible` for request-item rows: also the rows a client role reaches through
    `client_visible_only` or `assigned_only` (SPEC-020; TASK-035 D2). Agrees with `authorise`
    given each row's `ItemFacts`."""
    base = visible(ctx, action, engagement_id)
    if not isinstance(ctx, AuthContext):
        return base
    rule = _rule(action)
    reach: list[ColumnElement[bool]] = []
    for role, decision in rule.decisions.items():
        if decision not in _CLIENT_CONDITIONS or role not in CLIENT_ROLES:
            continue
        member_of = select(engagement_members.c.engagement_id).where(
            engagement_members.c.tenant_id == ctx.tenant_id,
            engagement_members.c.user_id == ctx.user_id,
            engagement_members.c.role == role,
        )
        rows = (
            client_visible.is_(True)
            if decision == "client_visible_only"
            else and_(client_visible.is_(True), client_assignee == ctx.user_id)
        )
        reach.append(and_(engagement_id.in_(member_of), rows))
    if not reach:
        return base
    return or_(base, and_(or_(*reach), _not_walled(ctx, engagement_id)))


__all__ = [
    "MFA_RECENT",
    "WALL_SAFE",
    "Forbidden",
    "ItemFacts",
    "Resource",
    "UnknownAction",
    "authorise",
    "authorise_items",
    "policy_agent_may_hold",
    "recording_checks",
    "register_active_engagements",
    "register_engagement_client",
    "register_independence",
    "serving_request",
    "visible",
    "visible_items",
]
