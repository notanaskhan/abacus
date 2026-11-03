"""Q-03-T064 part 2 (TASK-2824): the identity/authz survivors in `_condition_facts` and
`_consents_held`.

From the contracts in `identity.authz` and `authz.conditions`: `_condition_facts` reads only the
facts a rule's conditions name, through the registered lookups, and leaves every other fact
`None` (a condition with no fact denies, fail closed):
- `level` and `offshore` from the person's membership, when the rule names `level_in` or
  `not_offshore` (the membership passed in is used before a fresh read);
- `functions` from the functions lookup for the resource's work item;
- `scope_covered` from the scope lookup, for a client actor on an engagement;
- the target facts (`preparer`, `reserved_holder`, `owner`) only for a person who is not support,
  each only when the target carries what it needs; the owner is the named owner and a partner
  member now;
- `attest_client` and `gates` for any actor, from their lookups on the resource's engagement;
- `consents`, the purposes every data subject of the target holds now (`_consents_held`; `None`
  without subjects).
Each test pins every fact and every argument a lookup is called with.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.authz import Resource, TargetFacts
from abacus.modules.identity.authz.conditions import LOOKUPS, ConditionFacts
from abacus.modules.identity.authz.matrix import Rule
from abacus.modules.identity.context import Actor, AuthContext
from abacus.modules.identity.repository import MemberFacts

_condition_facts = authz._condition_facts  # pyright: ignore[reportPrivateUsage] -- the rule under test
_consents_held = authz._consents_held  # pyright: ignore[reportPrivateUsage] -- the rule under test

TENANT = uuid.uuid4()
ENGAGEMENT, WORK_ITEM, CLIENT = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
OWNER = uuid.uuid4()
NOW = datetime(2027, 9, 1, 12, tzinfo=UTC)
MEMBER = MemberFacts(level="manager", offshore=True, service_lines=frozenset(), client=False)


@dataclass
class Calls:
    member: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    functions: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    scope: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    attest: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    gates: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    reserved: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    partner: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    consent: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[Calls]:
    seen = Calls()
    state: dict[str, Any] = {"member": MEMBER, "partner": True, "given": set()}  # Any: knobs

    async def member_facts(tenant: object, user_id: object) -> MemberFacts | None:
        seen.member.append((tenant, user_id))
        return cast(MemberFacts | None, state["member"])

    async def functions(tenant: object, work_item: object, user: object) -> frozenset[str]:
        seen.functions.append((tenant, work_item, user))
        return frozenset({"preparer"})

    async def scope(tenant: object, user: object, engagement: object, work_item: object) -> bool:
        seen.scope.append((tenant, user, engagement, work_item))
        return True

    async def attest(tenant: object, engagement: object) -> bool:
        seen.attest.append((tenant, engagement))
        return True

    async def gates(tenant: object, engagement: object, names: object) -> dict[str, bool]:
        seen.gates.append((tenant, engagement, names))
        return {"G4": True}

    async def holds_reserved(ctx: object, resource: object, target: object, roles: object) -> bool:
        seen.reserved.append((ctx, resource, target, roles))
        return True

    async def partner_level(ctx: object) -> bool:
        seen.partner.append((ctx,))
        return bool(state["partner"])

    async def consent_given(tenant: object, entity: object, purpose: str, at: object) -> bool:
        seen.consent.append((tenant, entity, purpose, at))
        return (entity, purpose) in cast(set[tuple[object, str]], state["given"])

    monkeypatch.setattr(authz, "member_facts", member_facts)
    monkeypatch.setattr(authz, "_holds_reserved", holds_reserved)
    monkeypatch.setattr(authz, "_partner_level", partner_level)
    monkeypatch.setattr(authz, "consent_given", consent_given)
    monkeypatch.setattr(authz, "system_now", lambda: NOW)
    monkeypatch.setattr(LOOKUPS, "functions", functions)
    monkeypatch.setattr(LOOKUPS, "scope", scope)
    monkeypatch.setattr(LOOKUPS, "attest", attest)
    monkeypatch.setattr(LOOKUPS, "gates", gates)
    seen.__dict__["state"] = state
    yield seen


def _state(calls: Calls) -> dict[str, Any]:  # Any: the fixture's knobs
    return cast(dict[str, Any], calls.__dict__["state"])


def _rule(**conditions: object) -> Rule:
    return Rule(
        action="q03t064.facts",
        decisions={},
        mfa_recent=False,
        requires_reason=False,
        notify=False,
        **conditions,  # pyright: ignore[reportArgumentType] -- the conditions under test
    )


def _person(kind: str = "human", user: UUID | None = None) -> AuthContext:
    who = user or uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, kind, str(who)),  # pyright: ignore[reportArgumentType] -- test kinds
        who,
        uuid.uuid4(),
        None,
        NOW,
    )


def _resource(target: TargetFacts | None = None, **over: object) -> Resource:
    values: dict[str, object] = {
        "tenant_id": TENANT,
        "engagement_id": ENGAGEMENT,
        "archived": False,
        "client_id": CLIENT,
        "work_item_id": WORK_ITEM,
        "target": target,
    }
    values.update(over)
    return Resource(**values)  # pyright: ignore[reportArgumentType] -- the resource under test


EVERYTHING = _rule(
    level_in=frozenset({"manager"}),
    function_in=frozenset({"preparer"}),
    not_offshore=True,
    attest_client="deny",
    gates_met=("G4",),
    scope_only=True,
    not_preparer_of_target=True,
    reserved_role=True,
    owner_of_target=True,
    consent=frozenset({"use"}),
)


async def test_a_rule_with_no_conditions_reads_nothing_and_knows_nothing(calls: Calls) -> None:
    facts = await _condition_facts(_person(), _resource(), _rule(), {"manager"}, None)
    assert facts == ConditionFacts()
    assert calls == Calls()  # no lookup was asked anything


async def test_every_condition_reads_its_fact_with_the_right_arguments(calls: Calls) -> None:
    person = _person(user=OWNER)
    subject = uuid.uuid4()
    target = TargetFacts(
        preparer_user_ids=frozenset({OWNER}),
        reserved_role="engagement_partner",
        owner_user_id=OWNER,
        consent_subjects=frozenset({subject}),
    )
    _state(calls)["given"] = {(subject, "use")}
    resource = _resource(target)
    roles = {"client_admin"}
    facts = await _condition_facts(person, resource, EVERYTHING, roles, None)
    assert facts == ConditionFacts(
        level="manager",
        offshore=True,
        functions=frozenset({"preparer"}),
        attest_client=True,
        gates={"G4": True},
        scope_covered=True,
        client_actor=True,
        preparer=True,
        reserved_holder=True,
        owner=True,
        consents=frozenset({"use"}),
    )
    assert calls.member == [(person.tenant, OWNER)]
    assert calls.functions == [(person.tenant, WORK_ITEM, OWNER)]
    assert calls.scope == [(person.tenant, OWNER, ENGAGEMENT, WORK_ITEM)]
    assert calls.attest == [(person.tenant, ENGAGEMENT)]
    assert calls.gates == [(person.tenant, ENGAGEMENT, ("G4",))]
    assert calls.reserved == [(person, resource, target, roles)]
    assert calls.partner == [(person,)]
    assert calls.consent == [(person.tenant, subject, "use", NOW)]


async def test_the_membership_passed_in_is_used_before_a_fresh_read(calls: Calls) -> None:
    given = MemberFacts(level="partner", offshore=False, service_lines=frozenset(), client=False)
    facts = await _condition_facts(
        _person(), _resource(), _rule(level_in=frozenset({"partner"})), set(), given
    )
    assert (facts.level, facts.offshore) == ("partner", False)
    assert calls.member == []


@pytest.mark.parametrize("rule", [_rule(level_in=frozenset({"x"})), _rule(not_offshore=True)])
async def test_either_membership_condition_reads_the_membership(calls: Calls, rule: Rule) -> None:
    facts = await _condition_facts(_person(), _resource(), rule, set(), None)
    assert (facts.level, facts.offshore) == ("manager", True)
    assert len(calls.member) == 1


async def test_no_membership_leaves_level_and_offshore_unknown(calls: Calls) -> None:
    _state(calls)["member"] = None
    facts = await _condition_facts(_person(), _resource(), _rule(not_offshore=True), set(), None)
    assert (facts.level, facts.offshore) == (None, None)


async def test_functions_need_a_work_item_and_a_lookup(
    calls: Calls, monkeypatch: pytest.MonkeyPatch
) -> None:
    rule = _rule(function_in=frozenset({"preparer"}))
    no_item = await _condition_facts(_person(), _resource(work_item_id=None), rule, set(), None)
    assert no_item.functions is None and calls.functions == []
    monkeypatch.setattr(LOOKUPS, "functions", None)
    no_lookup = await _condition_facts(_person(), _resource(), rule, set(), None)
    assert no_lookup.functions is None


@pytest.mark.parametrize(
    ("roles", "engagement", "covered"),
    [
        ({"client_admin"}, ENGAGEMENT, True),
        ({"third_party"}, ENGAGEMENT, True),  # a third party is a client actor too
        ({"manager"}, ENGAGEMENT, None),  # not a client actor
        ({"client_admin"}, None, None),  # no engagement
    ],
)
async def test_scope_is_read_for_a_client_actor_on_an_engagement(
    calls: Calls, roles: set[str], engagement: UUID | None, covered: bool | None
) -> None:
    facts = await _condition_facts(
        _person(), _resource(engagement_id=engagement), _rule(scope_only=True), roles, None
    )
    assert facts.scope_covered is covered
    assert facts.client_actor is bool(roles & authz.CLIENT_ACTOR_ROLES)
    assert len(calls.scope) == (1 if covered else 0)


async def test_scope_needs_its_lookup(calls: Calls, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(LOOKUPS, "scope", None)
    facts = await _condition_facts(
        _person(), _resource(), _rule(scope_only=True), {"client_admin"}, None
    )
    assert facts.scope_covered is None


async def test_support_never_meets_a_target_condition(calls: Calls) -> None:
    target = TargetFacts(
        preparer_user_ids=frozenset(), reserved_role="manager", owner_user_id=OWNER
    )
    facts = await _condition_facts(
        _person("support", OWNER), _resource(target), EVERYTHING, {"manager"}, None
    )
    assert (facts.preparer, facts.reserved_holder, facts.owner) == (None, None, None)
    assert calls.reserved == [] and calls.partner == []


async def test_no_target_means_no_target_facts(calls: Calls) -> None:
    facts = await _condition_facts(_person(), _resource(None), EVERYTHING, {"manager"}, None)
    assert (facts.preparer, facts.reserved_holder, facts.owner, facts.consents) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    ("preparers", "expected"),
    [(frozenset({OWNER}), True), (frozenset({uuid.uuid4()}), False), (None, None)],
)
async def test_the_preparer_fact_is_membership_of_the_preparers(
    calls: Calls, preparers: frozenset[UUID] | None, expected: bool | None
) -> None:
    rule = _rule(not_preparer_of_target=True)
    target = TargetFacts(preparer_user_ids=preparers)
    facts = await _condition_facts(_person(user=OWNER), _resource(target), rule, set(), None)
    assert facts.preparer is expected


async def test_the_preparer_fact_needs_its_condition(calls: Calls) -> None:
    target = TargetFacts(preparer_user_ids=frozenset({OWNER}))
    facts = await _condition_facts(_person(user=OWNER), _resource(target), _rule(), set(), None)
    assert facts.preparer is None


async def test_a_reserved_holder_needs_a_reserved_role_on_the_target(calls: Calls) -> None:
    rule = _rule(reserved_role=True)
    none = await _condition_facts(_person(), _resource(TargetFacts()), rule, set(), None)
    assert none.reserved_holder is None and calls.reserved == []
    unasked = await _condition_facts(
        _person(), _resource(TargetFacts(reserved_role="manager")), _rule(), set(), None
    )
    assert unasked.reserved_holder is None and calls.reserved == []


@pytest.mark.parametrize(
    ("owner", "partner", "expected", "asked"),
    [
        (OWNER, True, True, True),
        (OWNER, False, False, True),  # a former partner who still owns it
        (uuid.uuid4(), True, False, False),  # someone else's: the partner check is not made
    ],
)
async def test_the_owner_is_the_named_owner_and_a_partner_now(
    calls: Calls, owner: UUID, partner: bool, expected: bool, asked: bool
) -> None:
    _state(calls)["partner"] = partner
    rule = _rule(owner_of_target=True)
    facts = await _condition_facts(
        _person(user=OWNER), _resource(TargetFacts(owner_user_id=owner)), rule, set(), None
    )
    assert facts.owner is expected
    assert len(calls.partner) == (1 if asked else 0)


async def test_the_owner_fact_needs_a_named_owner_and_its_condition(calls: Calls) -> None:
    unnamed = await _condition_facts(
        _person(), _resource(TargetFacts()), _rule(owner_of_target=True), set(), None
    )
    unasked = await _condition_facts(
        _person(user=OWNER), _resource(TargetFacts(owner_user_id=OWNER)), _rule(), set(), None
    )
    assert unnamed.owner is None and unasked.owner is None and calls.partner == []


async def test_an_agent_or_system_actor_still_gets_attest_gates_and_consents(
    calls: Calls,
) -> None:
    subject = uuid.uuid4()
    _state(calls)["given"] = {(subject, "use")}
    actor = cast(Actor, SimpleNamespace(tenant=TenantContext(TENANT, "system", "q03t064")))
    target = TargetFacts(
        preparer_user_ids=frozenset(),
        reserved_role="manager",
        owner_user_id=OWNER,
        consent_subjects=frozenset({subject}),
    )
    facts = await _condition_facts(actor, _resource(target), EVERYTHING, set(), None)
    assert facts == ConditionFacts(
        attest_client=True,
        gates={"G4": True},
        consents=frozenset({"use"}),
    )
    assert calls.member == [] and calls.functions == [] and calls.scope == []


@pytest.mark.parametrize("missing", ["engagement", "lookup", "condition"])
async def test_attest_and_gates_need_an_engagement_a_lookup_and_their_condition(
    calls: Calls, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    rule = _rule(attest_client="only", gates_met=("G4",))
    resource = _resource()
    if missing == "engagement":
        resource = _resource(engagement_id=None)
    elif missing == "lookup":
        monkeypatch.setattr(LOOKUPS, "attest", None)
        monkeypatch.setattr(LOOKUPS, "gates", None)
    else:
        rule = _rule()
    facts = await _condition_facts(_person(), resource, rule, set(), None)
    assert (facts.attest_client, facts.gates) == (None, None)


async def test_consents_need_their_condition(calls: Calls) -> None:
    target = TargetFacts(consent_subjects=frozenset({uuid.uuid4()}))
    facts = await _condition_facts(_person(), _resource(target), _rule(), set(), None)
    assert facts.consents is None and calls.consent == []


# --- _consents_held ------------------------------------------------------------------------------


async def test_no_subjects_holds_nothing_known(calls: Calls) -> None:
    person = _person()
    assert await _consents_held(person, _resource(None), frozenset({"use"})) is None
    no_subjects = _resource(TargetFacts(consent_subjects=frozenset()))
    assert await _consents_held(person, no_subjects, frozenset({"use"})) is None
    assert await _consents_held(person, _resource(TargetFacts()), frozenset({"use"})) is None
    assert calls.consent == []


async def test_a_purpose_is_held_only_when_every_subject_holds_it(calls: Calls) -> None:
    first, second = sorted([uuid.uuid4(), uuid.uuid4()])
    _state(calls)["given"] = {(first, "use"), (second, "use"), (first, "disclose")}
    person = _person()
    resource = _resource(TargetFacts(consent_subjects=frozenset({first, second})))
    held = await _consents_held(person, resource, frozenset({"use", "disclose"}))
    assert held == frozenset({"use"})
    # Every purpose is read for every subject, in order, at one instant.
    assert calls.consent == [
        (person.tenant, first, "disclose", NOW),
        (person.tenant, second, "disclose", NOW),
        (person.tenant, first, "use", NOW),
        (person.tenant, second, "use", NOW),
    ]


async def test_no_consent_held_is_an_empty_set_not_unknown(calls: Calls) -> None:
    resource = _resource(TargetFacts(consent_subjects=frozenset({uuid.uuid4()})))
    assert await _consents_held(_person(), resource, frozenset({"use"})) == frozenset()
