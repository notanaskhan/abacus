"""Matrix conditions (F-03-T24; chapter 03 §4.4), evaluated in `authorise` layer 4. PROTECTED.

A condition narrows an allowed action; it never grants one. Each reads facts its owner registers
here (identity never imports another module): work-item functions, gates and the engagement's
client's attest flag (organisations' derived `is_attest_client`, DEC-128) from engagements, client
scopes from the client grants. A condition whose facts
are not registered, or not known for this resource, denies (fail closed).

- `level_in(...)`         the actor's membership level is one of these
- `function_in(...)`      the actor holds one of these functions on the target's work item
- `not_offshore`          the actor's membership is not offshore
- `attest_client: deny`   the engagement's client is not an attest client; `only`: it is
- `gates_met(G…)`         every gate named is met on the engagement
- `scope_only`            a client actor's grant covers the target's scope
- `in_scope` (a role's decision): a practice leader's or quality partner's service lines include
  the engagement's, and nothing else (Q-21).
- `firm_setting(<name>)` (a role's decision): the firm has the setting on.
- `not_preparer_of_target` (P-04-T15): the actor is not one of the target's preparers (the
  owner's preparers and the current L1 signers, carried on the resource as `TargetFacts`).
- `reserved_role` (P-04-T15): the actor holds the role a decision card is reserved to (an
  engagement role, or the `signer` function on the work item) and, when the card names a person,
  is that person.

The two target conditions are a person's: an agent or a system run never meets them, whatever its
initiator could do, and a support session never does either (its facts are not resolved).

`conditions_hold` is pure, so the generated allow and deny tests drive it directly.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext
from abacus.modules.identity.authz.matrix import Rule


@dataclass(frozen=True)
class ConditionFacts:
    """What the conditions read; None means not known, which fails closed."""

    level: str | None = None
    offshore: bool | None = None
    functions: frozenset[str] | None = None
    attest_client: bool | None = None
    gates: dict[str, bool] | None = None
    scope_covered: bool | None = None
    client_actor: bool = False
    # P-04-T15: whether the actor prepared the target; whether they hold its reserved role.
    preparer: bool | None = None
    reserved_holder: bool | None = None


def conditions_hold(rule: Rule, facts: ConditionFacts, *, person: bool) -> bool:
    """Whether every condition on `rule` holds. `person` is False for agents and system runs:
    the actor conditions (level, function, offshore) are their initiator's, checked when the
    initiator is authorised; the resource conditions apply to every actor. The target
    conditions (`not_preparer_of_target`, `reserved_role`) are a named person's: a non-person
    never meets them."""
    if (rule.not_preparer_of_target or rule.reserved_role) and not person:
        return False
    if person:
        if rule.not_preparer_of_target and facts.preparer is not False:
            return False
        if rule.reserved_role and facts.reserved_holder is not True:
            return False
        if rule.level_in and (facts.level is None or facts.level not in rule.level_in):
            return False
        if rule.function_in and (
            facts.functions is None or not (facts.functions & rule.function_in)
        ):
            return False
        if rule.not_offshore and facts.offshore is not False:
            return False
        if rule.scope_only and facts.client_actor and facts.scope_covered is not True:
            return False
    if rule.attest_client is not None:
        if facts.attest_client is None:
            return False
        if (rule.attest_client == "only") != facts.attest_client:
            return False
    if rule.gates_met:
        if facts.gates is None:
            return False
        if not all(facts.gates.get(gate) is True for gate in rule.gates_met):
            return False
    return True


# --- lookups the owning modules register ---------------------------------------------------------

FunctionsLookup = Callable[[TenantContext, UUID, UUID], Awaitable[frozenset[str]]]
AttestLookup = Callable[[TenantContext, UUID], Awaitable[bool | None]]
GatesLookup = Callable[[TenantContext, UUID, tuple[str, ...]], Awaitable[dict[str, bool]]]
ServiceLineLookup = Callable[[TenantContext, UUID], Awaitable[str | None]]
ScopeLookup = Callable[[TenantContext, UUID, UUID, UUID | None], Awaitable[bool]]


# P-07-T24 (ADR-164 item 3): the attest flag as a column, for `visible()` under `g2_blocks_view`:
# an engagement-ID column -> whether its client is an attest client.
AttestColumn = Callable[[ColumnElement[UUID] | QueryableAttribute[UUID]], ColumnElement[bool]]


@dataclass
class _Lookups:
    functions: FunctionsLookup | None = None
    attest: AttestLookup | None = None
    attest_column: AttestColumn | None = None
    gates: GatesLookup | None = None
    service_line: ServiceLineLookup | None = None
    scope: ScopeLookup | None = None


LOOKUPS = _Lookups()
_registered: dict[str, tuple[str, str]] = {}


def _once(name: str, fn: Callable[..., object]) -> None:
    """One lookup per fact. The same function again is a no-op (a module that is executed twice,
    such as a reloaded `api.py`); a different one is refused."""
    identity = (fn.__module__, fn.__qualname__)
    known = _registered.get(name)
    if known is not None and known != identity:
        raise RuntimeError(f"the {name} lookup is already registered")
    _registered[name] = identity


def register_work_item_functions(lookup: FunctionsLookup) -> None:
    """engagements: (tenant, work_item_id, user_id) -> the person's functions on the work item."""
    _once("functions", lookup)
    LOOKUPS.functions = lookup


def register_attest_client(lookup: AttestLookup) -> None:
    """engagements: (tenant, engagement_id) -> whether its client is an attest client."""
    _once("attest", lookup)
    LOOKUPS.attest = lookup


def register_attest_client_column(builder: AttestColumn) -> None:
    """engagements: an engagement-ID column -> whether its client is an attest client (SQL)."""
    _once("attest_column", builder)
    LOOKUPS.attest_column = builder


def register_gates(lookup: GatesLookup) -> None:
    """engagements: (tenant, engagement_id, gates) -> each gate met or not."""
    _once("gates", lookup)
    LOOKUPS.gates = lookup


def register_engagement_service_line(lookup: ServiceLineLookup) -> None:
    """engagements: (tenant, engagement_id) -> the engagement's service line."""
    _once("service_line", lookup)
    LOOKUPS.service_line = lookup


def register_client_scope(lookup: ScopeLookup) -> None:
    """client grants: (tenant, user, engagement, work item) -> whether a grant covers it."""
    _once("scope", lookup)
    LOOKUPS.scope = lookup
