"""`authorise` and `visible`: the only permission logic in the product (ADR-020, ADR-023, ADR-027).
PROTECTED. TASK-007 design §5.

    await authorise(ctx, "request_item.create", Resource(ctx.tenant_id, engagement_id=eng.id))
    q = select(Engagement).where(visible(ctx, "engagement.read_metadata", Engagement.id))

`authorise` evaluates four layers in order; any layer denying means deny, and deny is the default:
  1. tenancy        the resource belongs to the active tenant
  2. relationships  the roles the actor holds here: firm role, plus engagement role on the
                    resource's engagement (no relationship at all: deny)
  3. roles          the matrix decision for those roles; an explicit `deny` beats any `allow`
  3b. independence for an action marked `independence: required` (G2 v2: DEC-39, ADR-164),
                    a staff engagement role grants it to a person not cleared for the engagement
                    only where G2 doesn't apply: G2 applies when the engagement's client is an
                    attest client (unknown counts as attest) and the action is not a read, or is
                    a read and the firm has `g2_blocks_view` on (stricter only). Firm and client
                    roles, support and system runs aren't bound; agents are, through their
                    initiator. (SPEC-025's TASK-045 gated every read on every engagement.)
  4. attributes     archived engagements are read-only; `mfa_recent`; `requires: reason`;
                    `notify` obligations are met by the action's own event (SPEC-013)
An agent is also bounded by its initiator, checked live (ADR-025): the initiator must be allowed
the same action, or `AGENT_ONLY_REACH` for actions no human role holds (`AGENT_FIRM_REACH` on
the firm, for a firm-level agent: SPEC-035 Q3, TASK-074 D1). A firm-level agent (no engagement)
relates only to the firm; an engagement agent never to the firm.
`task_scope` for humans is not a grant: it denies. A person's `firm_setting(<key>)` allows when
the firm has switched <key> on (F-03-T24; registered keys only); `firm_setting(autonomy_policy)`
is an agent's (SPEC-027, TASK-051): allowed at the firm's Routine autonomy or higher, within the
agent's scope. A firm's policy overrides (`firm_policy_overrides`) narrow a cell to deny before
any of this, and never widen one (`overrides.py`). The client
conditions (SPEC-020, TASK-035 D2) need the item's facts on the resource (`ItemFacts`):
`client_visible_only` allows a client-visible item, `assigned_only` a client-visible item
assigned to the person. Without the facts they deny. `visible_items` is their list-query twin.

Ethical walls (ADR-026, SPEC-002) come before roles: a person walled off from a client is denied
every engagement of it, whatever their roles, and agents and system runs with them. The walled
clients are read once per request (`recording_checks`) and live on every step elsewhere.
Offshore is not a wall (DEC-52, F-03 section 4.4; narrowed by TASK-1207, DEC-319): an offshore
member works on clients like anyone else with the same role, and is refused only the actions that
carry the `not_offshore` condition (`tin.reveal`, `pii.reveal`), at the condition layer (403).
Client access (`access_expired`) arrives with client users.

A successful `authorise` (and every `visible` filter built) is recorded for the request being
served, so a route that returns a success without one fails closed (`routing.AbacusRoute`). The
guard hides the response; it can't undo a write, so authorise before doing anything.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator, Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, Select, and_, false, func, or_, select, true
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.modules.identity.authz.conditions import LOOKUPS, ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import G2_BLOCKS_VIEW, RULES, Rule
from abacus.modules.identity.authz.overrides import apply_override
from abacus.modules.identity.context import Actor, AgentContext, AuthContext, SystemContext
from abacus.modules.identity.repository import (
    CLIENT_ROLES,
    ENGAGEMENT_ROLES,
    FirmPolicy,
    MemberFacts,
    client_access_grants,
    client_grant_engagements,
    engagement_members,
    engagement_role,
    engagement_roles_in_firm,
    ethical_walls,
    firm_policy,
    firm_setting_values,
    member_facts,
    walled_clients,
)

MFA_RECENT = timedelta(minutes=15)
# Ethical walls (ADR-026; SPEC-002) are enforced below, before roles: the API may start in
# production (founder decision 2026-10-06: walls gate the first real firm).
WALL_SAFE = True
Layer = Literal[
    "tenancy",
    "wall",
    "relationship",
    # A client user with no relationship to an engagement: answered as if it did not exist
    # (F-03 story 5.2, DEC-43), so another client's engagement is never confirmed.
    "client_scope",
    "role",
    "independence",
    "condition",
    "attribute",
    "delegation",
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


async def engagement_client(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's client through the registered lookup; None when unregistered or unknown
    (callers fail closed)."""
    if _engagement_client is None:
        return None
    return await _engagement_client[1](tenant, engagement_id)


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
# A firm-level agent (TASK-074 D1: the guidance drafter on a template) acts on the firm's
# methodology: its initiator must still be allowed to read it.
AGENT_FIRM_REACH = "methodology.read"
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
# Each firm's policy overrides and firm settings, read once per request (F-03-T24).
_policies: ContextVar[dict[UUID, FirmPolicy] | None] = ContextVar(
    "abacus_authz_policies", default=None
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
class TargetFacts:
    """The reviewable or decision card acted on, for the target conditions (P-04-T15; DEC-216).
    The owning service reads them (review's `ReviewableFacts` and the target's current L1
    signers; the card's reserved role and person) and puts them on the resource. Without them a
    target condition denies (fail closed)."""

    preparer_user_ids: frozenset[UUID] | None = None
    reserved_role: str | None = None
    reserved_user_id: UUID | None = None


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
    # The work item acted on, for `function_in` and `scope_only` (F-03-T24).
    work_item_id: UUID | None = None
    # The reviewable or card acted on, for `not_preparer_of_target` and `reserved_role`.
    target: TargetFacts | None = None

    @classmethod
    def firm(cls, tenant_id: UUID) -> Resource:
        return cls(tenant_id, None, False)

    @classmethod
    def client(cls, tenant_id: UUID, client_id: UUID) -> Resource:
        """A firm-level action on one client (P-07-T09): the wall check names the client."""
        return cls(tenant_id, None, False, client_id=client_id)

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
    policies_token = _policies.set({})
    try:
        yield checked
    finally:
        _policies.reset(policies_token)
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
    if not _probing.get():
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


FIRM_PARTNER = "firm_partner"


async def _partner_level(ctx: AuthContext) -> bool:
    member = await member_facts(ctx.tenant, ctx.user_id)
    return member is not None and not member.client and member.level == "partner"


async def _roles(ctx: Actor, resource: Resource, rule: Rule) -> set[str]:
    if isinstance(ctx, AgentContext):
        # The run's engagement only; a firm-level run (no engagement) the firm only.
        return {"agent"} if resource.engagement_id == ctx.engagement_id else set()
    if isinstance(ctx, SystemContext):
        # The platform acts on its run's engagement only: anything else (another engagement, a
        # firm-level action) has no relationship.
        return {"system"} if resource.engagement_id == ctx.engagement_id else set()
    roles: set[str] = set()
    if ctx.firm_role is not None:
        roles.add(ctx.firm_role)
    if (
        resource.engagement_id is None
        and FIRM_PARTNER in rule.decisions
        and not ctx.is_support
        and await _partner_level(ctx)
    ):
        roles.add(FIRM_PARTNER)  # P-01-T04 (DEC-132): derived from the membership level
    if resource.engagement_id is not None:
        role = await _engagement_role_once(ctx, resource.engagement_id)
        if role is not None:
            roles.add(role)
    elif (
        rule.reads
        and not rule.scope_only
        and not ctx.is_support
        and (ctx.firm_role is None or rule.decisions.get(ctx.firm_role) != "allow")
    ):
        # A `scope_only` read names its target (INV-4): it is never granted from the person's
        # roles on other engagements (A-02 security review, DEC-316; `connection.read`).
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
        if resource.engagement_id is not None and isinstance(ctx, AuthContext) and ctx.client:
            raise _deny(ctx, action, "client_scope")
        raise _deny(ctx, action, "relationship")
    # 3. Roles. For an agent, `task_scope` grants only what its run declared (ADR-025). A firm's
    # policy override narrows a cell, never widens it (F-03-T24).
    policy = await _firm_policy(ctx)
    by_role = {
        role: _on_item(
            apply_override(rule.decisions.get(role), policy.overrides.get((action, role))),
            ctx,
            resource,
        )
        for role in roles
    }
    member: MemberFacts | None = None
    if (
        isinstance(ctx, AuthContext)
        and "in_scope" in by_role.values()
        and not {"allow", "deny"} & set(by_role.values())
    ):
        # F-03-T24: a practice leader's or quality partner's service lines include the
        # engagement's (Q-21). Resolved only when it decides: another role's allow or deny
        # settles the action without it.
        for role, decision in by_role.items():
            if decision == "in_scope":
                member, scoped = await _in_scope(ctx, role, resource, member)
                if scoped:
                    by_role[role] = "allow"
    # F-03-T24: a person's `firm_setting(<key>)` cell allows when the firm has switched <key> on.
    if isinstance(ctx, AuthContext) and FIRM_SETTING in by_role.values():
        named = dict(rule.firm_settings)
        for role, decision in by_role.items():
            if decision == FIRM_SETTING and named.get(role) in policy.settings_on:
                by_role[role] = "allow"
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
    # 3b. Independence (G2 v2: DEC-39, ADR-164 items 2 to 4): when only a staff engagement role
    # grants a marked action, a person not cleared for this engagement is refused where G2 applies
    # (`_g2_applies`): an attest client's engagement, for anything but a read, and for reads too
    # when the firm has `g2_blocks_view` on. Firm and client roles, break-glass support and system
    # runs aren't bound by it; an agent is, through its initiator below. A firm-level read (no
    # engagement) lists rows that `visible()` filters by the same rule, engagement by engagement.
    # The cleared answer is read first (once per request), so the attest flag is read only for a
    # person who isn't cleared.
    granting = {role for role, decision in by_role.items() if decision == "allow"}
    if (
        rule.independence
        and resource.engagement_id is not None
        and isinstance(ctx, AuthContext)
        and not ctx.is_support
        and granting <= ENGAGEMENT_ROLES
        and not await _confirmed_for(ctx, resource)
        and await _g2_applies(ctx, resource, rule, policy)
    ):
        raise _deny(ctx, action, "independence")
    # 3c. Conditions (F-03-T24; chapter 03 §4.4): narrow what the roles allowed; fail closed.
    if has_conditions(rule):
        facts = await _condition_facts(ctx, resource, rule, roles, member)
        if not conditions_hold(rule, facts, person=isinstance(ctx, AuthContext)):
            raise _deny(ctx, action, "condition")
    # An agent never exceeds the person it acts for (ADR-025 intersection), checked live.
    if isinstance(ctx, AgentContext):
        reach = AGENT_ONLY_REACH if resource.engagement_id is not None else AGENT_FIRM_REACH
        delegated = action if _human_held(rule) else reach
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
    # allowed_actions() leaves MFA recency and a reason to the moment of acting: the UI steps up.
    if (
        rule.mfa_recent
        and not _probing.get()
        and (mfa_at is None or system_now() - mfa_at > MFA_RECENT)
    ):
        raise _deny(ctx, action, "attribute")
    if rule.requires_reason and not _probing.get() and not (reason and reason.strip()):
        raise _deny(ctx, action, "attribute")
    # `notify` (SPEC-013): a person's action is allowed, and its service emits the event its
    # catalogue entry notifies on, in the same unit of work (today only `engagement.self_join`).
    # Agents and the platform never carry the obligation.
    if rule.notify and not isinstance(ctx, AuthContext):
        raise _deny(ctx, action, "attribute")
    if _probing.get():
        return  # allowed_actions(): evaluated, never recorded as the route's check
    _record(action)
    _log.info("authz.allowed", action=action, tenant_id=ctx.tenant_id, **_who(ctx))


# A `firm_setting(<key>)` cell's decision; `rule.firm_settings` names each role's key. An agent's
# only key is `autonomy_policy` (`follow_up.send`; the matrix refuses any other at import).
FIRM_SETTING = "firm_setting"
AUTONOMY_POLICY = FIRM_SETTING


async def _firm_policy(ctx: Actor) -> FirmPolicy:
    cache = _policies.get()
    policy = cache.get(ctx.tenant_id) if cache is not None else None
    if policy is None:
        policy = await firm_policy(ctx.tenant)
        if cache is not None:
            cache[ctx.tenant_id] = policy
    return policy


async def _autonomy_allows(ctx: AgentContext) -> bool:
    from abacus.modules.identity.firm_settings import (  # firm_settings imports authz
        autonomy_level,
    )

    return await autonomy_level(ctx.tenant_id) >= 1


# F-03-T30 (ADR-145): `allowed_actions()` evaluates the matrix without recording a check, and
# reads each person's engagement role once while it does.
_probing: ContextVar[bool] = ContextVar("abacus_authz_probing", default=False)
_probe_roles: ContextVar[dict[tuple[UUID, UUID], str | None] | None] = ContextVar(
    "abacus_authz_probe_roles", default=None
)


async def _engagement_role_once(ctx: AuthContext, engagement_id: UUID) -> str | None:
    cache = _probe_roles.get()
    key = (ctx.user_id, engagement_id)
    if cache is not None and key in cache:
        return cache[key]
    role = await engagement_role(ctx.tenant, ctx.user_id, engagement_id)
    if cache is not None:
        cache[key] = role
    return role


async def allowed_actions(
    ctx: Actor, resource: Resource, candidates: Iterable[str] | None = None
) -> frozenset[str]:
    """The actions `ctx` may take on `resource`, by every layer of `authorise` except fresh MFA
    and a stated reason (asked for when acting). Records no check, so a route can't pass its
    guard with it, and logs no denials. Powers `/v1/me/capabilities` and `allowed_actions` in
    record projections (ADR-145)."""
    probe = _probing.set(True)
    roles = _probe_roles.set({})
    try:
        allowed: set[str] = set()
        for action in sorted(candidates if candidates is not None else RULES):
            try:
                await authorise(ctx, action, resource, reason="capability")
            except Forbidden:
                continue
            allowed.add(action)
        return frozenset(allowed)
    finally:
        _probe_roles.reset(roles)
        _probing.reset(probe)


def has_conditions(rule: Rule) -> bool:
    return bool(
        rule.level_in
        or rule.function_in
        or rule.not_offshore
        or rule.attest_client is not None
        or rule.gates_met
        or rule.scope_only
        or rule.not_preparer_of_target
        or rule.reserved_role
    )


_SCOPED_ROLES = frozenset({"practice_leader", "quality_partner"})


async def _in_scope(
    ctx: AuthContext, role: str, resource: Resource, member: MemberFacts | None
) -> tuple[MemberFacts | None, bool]:
    """Whether `role`'s `in_scope` holds, and the member facts read on the way (read once)."""
    lookup = LOOKUPS.service_line
    if role not in _SCOPED_ROLES or resource.engagement_id is None or lookup is None:
        return member, False
    member = member or await member_facts(ctx.tenant, ctx.user_id)
    if member is None:
        return member, False
    line = await lookup(ctx.tenant, resource.engagement_id)
    return member, line is not None and line in member.service_lines


async def _condition_facts(
    ctx: Actor, resource: Resource, rule: Rule, roles: set[str], member: MemberFacts | None
) -> ConditionFacts:
    level: str | None = None
    offshore: bool | None = None
    functions: frozenset[str] | None = None
    scope_covered: bool | None = None
    preparer: bool | None = None
    reserved_holder: bool | None = None
    client_actor = bool(roles & CLIENT_ROLES)
    if isinstance(ctx, AuthContext):
        if rule.level_in or rule.not_offshore:
            member = member or await member_facts(ctx.tenant, ctx.user_id)
            if member is not None:
                level, offshore = member.level, member.offshore
        if rule.function_in and resource.work_item_id is not None and LOOKUPS.functions:
            functions = await LOOKUPS.functions(ctx.tenant, resource.work_item_id, ctx.user_id)
        if rule.scope_only and client_actor and resource.engagement_id and LOOKUPS.scope:
            scope_covered = await LOOKUPS.scope(
                ctx.tenant, ctx.user_id, resource.engagement_id, resource.work_item_id
            )
        target = resource.target
        if target is not None and not ctx.is_support:  # P-04-T15: support never meets them
            if rule.not_preparer_of_target and target.preparer_user_ids is not None:
                preparer = ctx.user_id in target.preparer_user_ids
            if rule.reserved_role and target.reserved_role is not None:
                reserved_holder = await _holds_reserved(ctx, resource, target, roles)
    attest: bool | None = None
    if rule.attest_client is not None and resource.engagement_id and LOOKUPS.attest:
        attest = await LOOKUPS.attest(ctx.tenant, resource.engagement_id)
    gates: dict[str, bool] | None = None
    if rule.gates_met and resource.engagement_id and LOOKUPS.gates:
        gates = await LOOKUPS.gates(ctx.tenant, resource.engagement_id, rule.gates_met)
    return ConditionFacts(
        level=level,
        offshore=offshore,
        functions=functions,
        attest_client=attest,
        gates=gates,
        scope_covered=scope_covered,
        client_actor=client_actor,
        preparer=preparer,
        reserved_holder=reserved_holder,
    )


# The function a `signer`-reserved card needs on its work item; the other reserved roles are
# engagement roles (review.slots `_RESERVED_ROLES`).
_SIGNER = "signer"


async def _holds_reserved(
    ctx: AuthContext, resource: Resource, target: TargetFacts, roles: set[str]
) -> bool:
    """P-04-T15: the person a card is reserved to, holding its role here now."""
    if target.reserved_user_id is not None and target.reserved_user_id != ctx.user_id:
        return False
    role = target.reserved_role
    if role == _SIGNER:
        if resource.work_item_id is None or LOOKUPS.functions is None:
            return False
        held = await LOOKUPS.functions(ctx.tenant, resource.work_item_id, ctx.user_id)
        return _SIGNER in held
    return role in roles and role in ENGAGEMENT_ROLES


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
    if resource.engagement_id is None and resource.client_id is None:
        return False  # a firm-level action names no client, so no wall applies
    # A client-level resource (`Resource.client`, P-07-T09) names its client: walled the same as
    # that client's engagements (ADR-026; S6 review, DEC-233).
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
    if client is None and resource.engagement_id is not None:
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


async def _g2_applies(ctx: Actor, resource: Resource, rule: Rule, policy: FirmPolicy) -> bool:
    """ADR-164 items 2 and 3: whether G2 binds this action here. A read is bound only when the
    firm has `g2_blocks_view` on; any action only on an attest client's engagement. An unknown or
    unregistered attest flag counts as attest (fail closed)."""
    if rule.reads and G2_BLOCKS_VIEW not in policy.settings_on:
        return False
    lookup = LOOKUPS.attest
    if lookup is None or resource.engagement_id is None:
        return True
    return await lookup(ctx.tenant, resource.engagement_id) is not False


def _g2_blocks_reads(ctx: AuthContext, engagement_id: EngagementColumn) -> ColumnElement[bool]:
    """`visible()`'s twin of `_g2_applies` for a read: the firm has `g2_blocks_view` on and the
    row's engagement's client is an attest client (unregistered: attest, fail closed)."""
    setting = (
        select(firm_setting_values.c.key)
        .where(
            firm_setting_values.c.tenant_id == ctx.tenant_id,
            firm_setting_values.c.key == G2_BLOCKS_VIEW,
            firm_setting_values.c.value.is_(True),
        )
        .exists()
    )
    attest = LOOKUPS.attest_column
    return and_(setting, attest(engagement_id)) if attest is not None else setting


def _not_walled(ctx: Actor, engagement_id: EngagementColumn) -> ColumnElement[bool]:
    """Rows whose engagement's client the acting person isn't walled off from (ADR-026)."""
    walls = select(ethical_walls.c.id).where(
        ethical_walls.c.tenant_id == ctx.tenant_id,
        ethical_walls.c.user_id == _person(ctx),
        ethical_walls.c.status == "active",
    )
    client = _engagement_client[0](engagement_id) if _engagement_client is not None else None
    if client is not None:
        walls = walls.where(ethical_walls.c.client_id == client)
    return ~walls.correlate_except(ethical_walls).exists()


def visible(ctx: Actor, action: str, engagement_id: EngagementColumn) -> ColumnElement[bool]:
    """A filter for list queries: rows whose engagement the actor may `action` (a read action),
    minus walled clients. Agrees with `authorise` for every role. Apply it: building it counts as
    the route's check."""
    by_role = _visible_by_role(ctx, action, engagement_id)
    if isinstance(ctx, AgentContext):
        return by_role  # the initiator's filter, inside, already excludes their walls
    return and_(by_role, _not_walled(ctx, engagement_id))


# F-03-T27 (ADR-145, P-06): the scope kind a list declares. `engagement` and `work_item` filter on
# the row's engagement; `client` and `client_entity` on the row's client (readable when the
# person may read content on at least one non-walled engagement of that client, or a firm role
# allows the action outright); `portal_scope` on a client user's grant for that scope.
ScopeKind = Literal["engagement", "work_item", "client", "client_entity", "portal_scope"]
SCOPE_KINDS: frozenset[str] = frozenset(
    {"engagement", "work_item", "client", "client_entity", "portal_scope"}
)
EngagementPredicate = Callable[[EngagementColumn], ColumnElement[bool]]
# engagements: the clients of the engagements a predicate admits, as a subquery.
ClientsOfEngagements = Callable[[EngagementPredicate], Select[UUID]]
_clients_of_engagements: ClientsOfEngagements | None = None


def register_clients_of_engagements(builder: ClientsOfEngagements) -> None:
    """engagements registers how to list the clients of the engagements a filter admits."""
    global _clients_of_engagements
    known = _clients_of_engagements
    if known is not None and (known.__module__, known.__qualname__) != (
        builder.__module__,
        builder.__qualname__,
    ):
        raise RuntimeError("the clients-of-engagements subquery is already registered")
    _clients_of_engagements = builder


def _not_walled_client(ctx: Actor, client_id: EngagementColumn) -> ColumnElement[bool]:
    """Rows whose client the acting person isn't walled off from (ADR-026; 404 everywhere)."""
    walls = select(ethical_walls.c.id).where(
        ethical_walls.c.tenant_id == ctx.tenant_id,
        ethical_walls.c.user_id == _person(ctx),
        ethical_walls.c.status == "active",
        ethical_walls.c.client_id == client_id,
    )
    return ~walls.correlate_except(ethical_walls).exists()


def visible_scope(
    ctx: Actor,
    action: str,
    scope: ScopeKind,
    column: EngagementColumn,
    *,
    grant_kind: str | None = None,
) -> ColumnElement[bool]:
    """`visible()` for a declared scope kind (ADR-145). `column` is the row's engagement id
    (`engagement`, `work_item`), its client id (`client`, `client_entity`) or its scope id
    (`portal_scope`, with `grant_kind` naming the grant's scope kind). Every kind excludes walled
    clients; an unregistered lookup admits nothing (fail closed). Building it records the check."""
    if scope in ("engagement", "work_item"):
        return visible(ctx, action, column)
    if scope in ("client", "client_entity"):
        rule = _rule(action)
        if not rule.reads:
            raise ValueError(f"visible() filters reads; {action!r} is not a read action")
        firm = (
            rule.decisions.get(ctx.firm_role)
            if isinstance(ctx, AuthContext) and ctx.firm_role is not None
            else None
        )
        if firm == "allow":
            _record(action)
            return _not_walled_client(ctx, column)
        if _clients_of_engagements is None:
            _record(action)
            return false()

        def admitted(engagement_id: EngagementColumn) -> ColumnElement[bool]:
            return visible(ctx, action, engagement_id)

        return and_(
            column.in_(_clients_of_engagements(admitted).scalar_subquery()),
            _not_walled_client(ctx, column),
        )
    if scope == "portal_scope":
        _rule(action)
        _record(action)
        if not isinstance(ctx, AuthContext) or grant_kind is None:
            return false()
        granted = select(client_access_grants.c.scope_id).where(
            client_access_grants.c.tenant_id == ctx.tenant_id,
            client_access_grants.c.user_id == ctx.user_id,
            client_access_grants.c.scope_kind == grant_kind,
            client_access_grants.c.status == "active",
            or_(
                client_access_grants.c.expires_at.is_(None),
                client_access_grants.c.expires_at > func.clock_timestamp(),
            ),
        )
        return column.in_(granted.scalar_subquery())
    raise ValueError(f"unknown scope kind {scope!r}")


async def visible_clients(
    ctx: Actor, action: str, client_id: EngagementColumn
) -> ColumnElement[bool]:
    """`visible_scope(ctx, action, "client", client_id)` with the derived `firm_partner` cell
    (DEC-132, DEC-141): a partner-level member whose firm role doesn't already allow the read
    reads every client they aren't walled off from. Async: the membership level is read."""
    rule = _rule(action)
    if not rule.reads:
        raise ValueError(f"visible() filters reads; {action!r} is not a read action")
    if (
        isinstance(ctx, AuthContext)
        and rule.decisions.get(FIRM_PARTNER) == "allow"
        and not ctx.is_support
        and (ctx.firm_role is None or rule.decisions.get(ctx.firm_role) != "allow")
        and await _partner_level(ctx)
    ):
        _record(action)
        return _not_walled_client(ctx, client_id)
    return visible_scope(ctx, action, "client", client_id)


def _visible_by_role(
    ctx: Actor, action: str, engagement_id: EngagementColumn
) -> ColumnElement[bool]:
    rule = _rule(action)
    if not rule.reads:
        raise ValueError(f"visible() filters reads; {action!r} is not a read action")
    if rule.mfa_recent or rule.requires_reason or rule.notify or has_conditions(rule):
        raise ValueError(f"visible() can't apply {action!r}'s conditions; use authorise()")
    _record(action)
    if isinstance(ctx, AgentContext):
        agent = rule.decisions.get("agent")
        if not (agent == "allow" or (agent == "task_scope" and action in ctx.task_scope)):
            return false()
        if ctx.engagement_id is None:
            return false()  # a firm-level agent lists no engagement's rows
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
        # G2 v2 (ADR-164): a staff engagement role reaches a marked read unless the person isn't
        # cleared and the firm's `g2_blocks_view` applies to the row's attest-client engagement.
        # Unregistered, the confirmations can't be read and staff reach nothing (fail closed).
        reach = [_member_of(ctx, engagement_id, client)] if client else []
        if staff and _independence is not None:
            confirmed = _independence[0](engagement_id, ctx.user_id)
            cleared = or_(confirmed, ~_g2_blocks_reads(ctx, engagement_id))
            reach.append(and_(_member_of(ctx, engagement_id, staff), cleared))
        return or_(*reach) if reach else false()
    if not staff and not client:
        return false()
    return _member_of(ctx, engagement_id, staff + client)


def _member_of(
    ctx: AuthContext, engagement_id: EngagementColumn, roles: list[str]
) -> ColumnElement[bool]:
    """Engagements where the person holds one of `roles`: staff roles from the team, client
    roles from their engagement-scope grants (F-03-T26)."""
    staff = [role for role in roles if role not in CLIENT_ROLES]
    client = [role for role in roles if role in CLIENT_ROLES]
    reach: list[ColumnElement[bool]] = []
    if staff:
        member_of = select(engagement_members.c.engagement_id).where(
            engagement_members.c.tenant_id == ctx.tenant_id,
            engagement_members.c.user_id == ctx.user_id,
            engagement_members.c.role.in_(staff),
        )
        reach.append(engagement_id.in_(member_of))
    if client:
        reach.append(
            engagement_id.in_(client_grant_engagements(ctx.tenant_id, ctx.user_id, client))
        )
    return or_(*reach) if reach else false()


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
        member_of = client_grant_engagements(ctx.tenant_id, ctx.user_id, [role])
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
    "visible_clients",
    "visible_items",
]
