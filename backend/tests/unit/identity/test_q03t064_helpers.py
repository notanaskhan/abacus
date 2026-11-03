"""Q-03-T064 part 2 (TASK-2824): the identity/authz survivors in the smaller helpers and the
wrappers around `authorise` (`authorise_on_condition`, `authorise_with_scope`,
`allowed_actions`, `_partner_level`, `_manager_level`, `_in_scope`, `_holds_reserved`,
`_engagement_roles_in_firm`, `engagement_client`, `_who`).

From the contracts in `identity.authz`:
- `authorise_on_condition` answers `None` when allowed outright; when the role layer refuses a
  person, it answers the client condition (`assigned_only`, `client_visible_only`,
  `delegated_only`) one of their roles holds, recording the check; anything else is refused;
- `authorise_with_scope` lets a person's firm-level scope stand in where the roles refuse; never
  the agent, the system or support;
- `allowed_actions` lists what passes every layer, probing quietly (no denial is logged and the
  probe flags are reset);
- the levels are a non-client member's `partner` or `manager` level;
- `in_scope` holds for a practice leader or quality partner whose service lines include the
  engagement's line;
- a reserved card is held by its reserved person (if named) holding its role here, a `signer`
  card by the work item's signer function;
- the firm-wide engagement roles are read once per request and fail closed.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.authz import Forbidden, Resource, TargetFacts
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import Actor, AgentContext, AuthContext
from abacus.modules.identity.repository import MemberFacts

TENANT, ENGAGEMENT, WORK_ITEM = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
ACTION = "q03t064h.update"
NOW = datetime(2027, 9, 1, 12, tzinfo=UTC)

_partner_level = authz._partner_level  # pyright: ignore[reportPrivateUsage] -- the rule under test
_manager_level = authz._manager_level  # pyright: ignore[reportPrivateUsage] -- the rule under test
_in_scope = authz._in_scope  # pyright: ignore[reportPrivateUsage] -- the rule under test
_holds_reserved = authz._holds_reserved  # pyright: ignore[reportPrivateUsage] -- the rule under test
_engagement_roles_in_firm = authz._engagement_roles_in_firm  # pyright: ignore[reportPrivateUsage] -- the rule under test
_who = authz._who  # pyright: ignore[reportPrivateUsage] -- the rule under test


def _person(kind: str = "human", user: uuid.UUID | None = None) -> AuthContext:
    who = user or uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, kind, str(who)),  # pyright: ignore[reportArgumentType] -- test kinds
        who,
        uuid.uuid4(),
        None,
        NOW,
    )


def _agent() -> AgentContext:
    initiator = _person()
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(TENANT, "agent", f"agent:q03.agent:{run}"),
        agent_id="q03.agent",
        agent_run_id=run,
        engagement_id=ENGAGEMENT,
        task_scope=frozenset(),
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


def _member(
    level: str | None, *, client: bool = False, lines: frozenset[str] = frozenset()
) -> MemberFacts:
    return MemberFacts(level=level, offshore=False, service_lines=lines, client=client)


def _install(monkeypatch: pytest.MonkeyPatch, decisions: dict[str, str]) -> None:
    rule = Rule(
        action=ACTION,
        decisions=decisions,  # pyright: ignore[reportArgumentType] -- test cells
        mfa_recent=False,
        requires_reason=False,
        notify=False,
    )
    monkeypatch.setitem(RULES, ACTION, rule)


RESOURCE = Resource.engagement(TENANT, ENGAGEMENT, archived=False)


# --- authorise_on_condition ----------------------------------------------------------------------


@pytest.fixture
def refusing(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, object]]:
    """`authorise` refuses at the layer the test sets (or allows with `None`)."""
    knobs: dict[str, object] = {"layer": "role", "roles": {"client_admin"}}

    async def authorise(*_: object, **__: object) -> None:
        if knobs["layer"] is not None:
            raise Forbidden(ACTION, knobs["layer"])  # pyright: ignore[reportArgumentType] -- test layers

    async def roles(*_: object) -> set[str]:
        return set(cast(set[str], knobs["roles"]))

    monkeypatch.setattr(authz, "authorise", authorise)
    monkeypatch.setattr(authz, "_roles", roles)
    yield knobs


async def test_allowed_outright_answers_none(
    refusing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"client_admin": "assigned_only"})
    refusing["layer"] = None
    assert await authz.authorise_on_condition(_person(), ACTION, RESOURCE) is None


@pytest.mark.parametrize("condition", ["assigned_only", "client_visible_only", "delegated_only"])
async def test_a_role_refusal_answers_the_client_condition_held(
    refusing: dict[str, object], monkeypatch: pytest.MonkeyPatch, condition: str
) -> None:
    _install(monkeypatch, {"client_admin": condition, "manager": "allow"})
    with authz.recording_checks() as checked:
        held = await authz.authorise_on_condition(_person(), ACTION, RESOURCE)
    assert held == condition
    assert checked == {ACTION}


async def test_no_client_condition_held_is_refused(
    refusing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"client_admin": "deny"})
    with pytest.raises(Forbidden):
        await authz.authorise_on_condition(_person(), ACTION, RESOURCE)


@pytest.mark.parametrize("layer", ["wall", "relationship", "condition"])
async def test_a_refusal_outside_the_role_layer_stands(
    refusing: dict[str, object], monkeypatch: pytest.MonkeyPatch, layer: str
) -> None:
    _install(monkeypatch, {"client_admin": "assigned_only"})
    refusing["layer"] = layer
    with pytest.raises(Forbidden) as caught:
        await authz.authorise_on_condition(_person(), ACTION, RESOURCE)
    assert caught.value.layer == layer


async def test_an_agent_never_holds_a_client_condition(
    refusing: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, {"client_admin": "assigned_only", "agent": "assigned_only"})
    with pytest.raises(Forbidden):
        await authz.authorise_on_condition(_agent(), ACTION, RESOURCE)


async def test_an_unknown_action_is_an_error_before_anything(refusing: dict[str, object]) -> None:
    with pytest.raises(authz.UnknownAction):
        await authz.authorise_on_condition(_person(), "q03t064h.unheard_of", RESOURCE)


# --- authorise_with_scope ------------------------------------------------------------------------


async def test_the_roles_allowing_needs_no_scope(refusing: dict[str, object]) -> None:
    refusing["layer"] = None
    await authz.authorise_with_scope(_person(), ACTION, RESOURCE, in_scope=False)


async def test_a_persons_scope_stands_in_and_records_the_check(
    refusing: dict[str, object],
) -> None:
    with authz.recording_checks() as checked:
        await authz.authorise_with_scope(_person(), ACTION, RESOURCE, in_scope=True)
    assert checked == {ACTION}


@pytest.mark.parametrize(
    ("kind", "in_scope"), [("human", False), ("support", True), ("agent", True)]
)
async def test_the_scope_never_grants_outside_a_person_in_scope(
    refusing: dict[str, object], kind: str, in_scope: bool
) -> None:
    with pytest.raises(Forbidden):
        await authz.authorise_with_scope(_person(kind), ACTION, RESOURCE, in_scope=in_scope)


# --- allowed_actions -----------------------------------------------------------------------------


async def test_allowed_actions_lists_what_passes_and_probes_quietly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, object, bool]] = []

    async def authorise(ctx: Actor, action: str, resource: Resource, **kw: object) -> None:
        seen.append((action, kw.get("reason"), authz._probing.get()))  # pyright: ignore[reportPrivateUsage] -- the probe flag
        if action.endswith("no"):
            raise Forbidden(action, "role")

    monkeypatch.setattr(authz, "authorise", authorise)
    got = await authz.allowed_actions(_person(), RESOURCE, ["b.yes", "a.no", "c.yes"])
    assert got == frozenset({"b.yes", "c.yes"})
    assert [s[0] for s in seen] == ["a.no", "b.yes", "c.yes"]  # in sorted order
    assert {(s[1], s[2]) for s in seen} == {("capability", True)}
    assert authz._probing.get() is False  # pyright: ignore[reportPrivateUsage] -- reset after
    assert authz._probe_roles.get() is None  # pyright: ignore[reportPrivateUsage] -- reset after


async def test_allowed_actions_defaults_to_every_action(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def authorise(_ctx: Actor, action: str, *_: object, **__: object) -> None:
        seen.append(action)

    monkeypatch.setattr(authz, "authorise", authorise)
    got = await authz.allowed_actions(_person(), RESOURCE)
    assert got == frozenset(RULES) and seen == sorted(RULES)


# --- levels, scope and reserved cards ------------------------------------------------------------


@pytest.fixture
def member(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, object]]:
    knobs: dict[str, object] = {"member": None, "calls": []}

    async def member_facts(tenant: object, user: object) -> MemberFacts | None:
        knobs["calls"].append((tenant, user))  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType] -- the recorder
        return knobs["member"]  # pyright: ignore[reportReturnType] -- the knob

    monkeypatch.setattr(authz, "member_facts", member_facts)
    yield knobs


@pytest.mark.parametrize(
    ("facts", "partner", "manager"),
    [
        (_member("partner"), True, False),
        (_member("manager"), False, True),
        (_member("partner", client=True), False, False),
        (_member("manager", client=True), False, False),
        (_member(None), False, False),
        (None, False, False),
    ],
)
async def test_the_levels_are_a_non_client_members(
    member: dict[str, object], facts: MemberFacts | None, partner: bool, manager: bool
) -> None:
    member["member"] = facts
    person = _person()
    assert await _partner_level(person) is partner
    assert await _manager_level(person) is manager
    assert member["calls"] == [(person.tenant, person.user_id)] * 2


async def test_in_scope_holds_for_a_scoped_role_on_its_line(
    member: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[tuple[object, object]] = []

    async def line(tenant: object, engagement: object) -> str:
        asked.append((tenant, engagement))
        return "tax"

    monkeypatch.setattr(authz.LOOKUPS, "service_line", line)
    member["member"] = _member("partner", lines=frozenset({"tax"}))
    person = _person()
    facts, held = await _in_scope(person, "practice_leader", RESOURCE, None)
    assert held is True and facts == member["member"]
    assert asked == [(person.tenant, ENGAGEMENT)]
    given = _member("partner", lines=frozenset({"audit"}))
    facts, held = await _in_scope(person, "quality_partner", RESOURCE, given)
    assert (facts, held) == (given, False)
    assert (
        len(cast(list[object], member["calls"])) == 1
    )  # the membership passed in is not read again


@pytest.mark.parametrize("why", ["role", "engagement", "lookup", "member", "line"])
async def test_in_scope_fails_closed(
    member: dict[str, object], monkeypatch: pytest.MonkeyPatch, why: str
) -> None:
    async def line(*_: object) -> str | None:
        return None if why == "line" else "tax"

    monkeypatch.setattr(authz.LOOKUPS, "service_line", None if why == "lookup" else line)
    member["member"] = None if why == "member" else _member("partner", lines=frozenset({"tax"}))
    role = "manager" if why == "role" else "practice_leader"
    resource = Resource.firm(TENANT) if why == "engagement" else RESOURCE
    passed = _member("x") if why == "role" else None
    facts, held = await _in_scope(_person(), role, resource, passed)
    assert held is False
    if why in ("role", "engagement", "lookup"):
        assert facts is passed and member["calls"] == []


@pytest.mark.parametrize(
    ("reserved_to", "role", "roles", "held"),
    [
        ("me", "engagement_partner", {"engagement_partner"}, True),
        (None, "engagement_partner", {"engagement_partner"}, True),  # no person named
        ("other", "engagement_partner", {"engagement_partner"}, False),
        ("me", "engagement_partner", {"manager"}, False),  # not holding the role here
        ("me", "client_admin", {"client_admin"}, False),  # not an engagement role
    ],
)
async def test_a_reserved_card_is_its_persons_with_the_role_here(
    reserved_to: str | None, role: str, roles: set[str], held: bool
) -> None:
    person = _person()
    named = {"me": person.user_id, "other": uuid.uuid4(), None: None}[reserved_to]
    target = TargetFacts(reserved_role=role, reserved_user_id=named)
    assert await _holds_reserved(person, RESOURCE, target, roles) is held


async def test_a_signer_card_is_the_work_items_signer(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[object, ...]] = []

    async def functions(tenant: object, work_item: object, user: object) -> frozenset[str]:
        asked.append((tenant, work_item, user))
        return frozenset({"signer"})

    person = _person()
    target = TargetFacts(reserved_role="signer")
    on_item = Resource(TENANT, ENGAGEMENT, False, work_item_id=WORK_ITEM)
    monkeypatch.setattr(authz.LOOKUPS, "functions", None)
    assert await _holds_reserved(person, on_item, target, set()) is False
    monkeypatch.setattr(authz.LOOKUPS, "functions", functions)
    assert await _holds_reserved(person, RESOURCE, target, set()) is False  # no work item
    assert await _holds_reserved(person, on_item, target, set()) is True
    assert asked == [(person.tenant, WORK_ITEM, person.user_id)]


# --- firm-wide roles, the engagement's client, who is acting -------------------------------------


async def test_firm_roles_without_a_registration_are_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authz, "_active_engagements", None)
    assert await _engagement_roles_in_firm(_person()) == frozenset()


async def test_firm_roles_are_read_once_per_request_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: list[tuple[object, ...]] = []
    active = object()

    async def roles_in_firm(tenant: object, user: object, engagements: object) -> frozenset[str]:
        reads.append((tenant, user, engagements))
        return frozenset({"manager"})

    monkeypatch.setattr(authz, "_active_engagements", lambda: active)
    monkeypatch.setattr(authz, "engagement_roles_in_firm", roles_in_firm)
    person = _person()
    token = authz._firm_engagement_roles.set({})  # pyright: ignore[reportPrivateUsage] -- a request's cache
    try:
        assert await _engagement_roles_in_firm(person) == frozenset({"manager"})
        assert await _engagement_roles_in_firm(person) == frozenset({"manager"})
    finally:
        authz._firm_engagement_roles.reset(token)  # pyright: ignore[reportPrivateUsage] -- the cache
    assert reads == [(person.tenant, person.user_id, active)]

    async def broken(*_: object) -> frozenset[str]:
        raise RuntimeError("down")

    monkeypatch.setattr(authz, "engagement_roles_in_firm", broken)
    assert await _engagement_roles_in_firm(person) == frozenset()


async def test_the_engagement_client_needs_its_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    client = uuid.uuid4()
    tenant = TenantContext(TENANT, "system", "q03")
    monkeypatch.setattr(authz, "_engagement_client", None)
    assert await authz.engagement_client(tenant, ENGAGEMENT) is None

    async def lookup(t: object, e: object) -> uuid.UUID | None:
        return client if (t, e) == (tenant, ENGAGEMENT) else None

    monkeypatch.setattr(authz, "_engagement_client", (_same, lookup))
    assert await authz.engagement_client(tenant, ENGAGEMENT) == client


def _same(column: object) -> object:
    return column


def test_who_names_the_acting_person_or_run() -> None:
    person = _person()
    assert _who(person) == {"user_id": person.user_id}
    agent = _agent()
    assert _who(agent) == {
        "agent_id": "q03.agent",
        "agent_run_id": agent.agent_run_id,
        "on_behalf_of": agent.initiator.user_id,
    }
