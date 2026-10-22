"""F-03-T24 acceptance (first half): "Generated allow and deny tests exist for every new
condition" (chapter 03 §4.4). The cases are generated from one table, and a meta-test fails if a
condition the parser knows has no allow case or no deny case. Conditions narrow; missing facts
deny (fail closed)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz
from abacus.modules.identity.authz import Resource, matrix
from abacus.modules.identity.authz.conditions import ConditionFacts, conditions_hold
from abacus.modules.identity.authz.matrix import CONDITION_KEYS
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import MemberFacts

# The parser, tested directly (private by name only, as the matrix contract tests treat it).
_rule = matrix._rule  # pyright: ignore[reportPrivateUsage]  # the parser, tested directly

ALLOW = {"engagement_partner": "allow"}

# (condition, the action's entries, facts that satisfy it, facts that break it)
CASES: list[tuple[str, dict[str, str], ConditionFacts, ConditionFacts]] = [
    (
        "level_in",
        {**ALLOW, "level_in": "partner,manager"},
        ConditionFacts(level="manager"),
        ConditionFacts(level="senior"),
    ),
    (
        "level_in",
        {**ALLOW, "level_in": "partner"},
        ConditionFacts(level="partner"),
        ConditionFacts(level=None),
    ),
    (
        "function_in",
        {**ALLOW, "function_in": "signer,eqr"},
        ConditionFacts(functions=frozenset({"preparer", "signer"})),
        ConditionFacts(functions=frozenset({"preparer"})),
    ),
    (
        "function_in",
        {**ALLOW, "function_in": "signer"},
        ConditionFacts(functions=frozenset({"signer"})),
        ConditionFacts(functions=None),
    ),
    (
        "not_offshore",
        {**ALLOW, "not_offshore": "required"},
        ConditionFacts(offshore=False),
        ConditionFacts(offshore=True),
    ),
    (
        "not_offshore",
        {**ALLOW, "not_offshore": "required"},
        ConditionFacts(offshore=False),
        ConditionFacts(offshore=None),
    ),
    (
        "attest_client",
        {**ALLOW, "attest_client": "deny"},
        ConditionFacts(attest_client=False),
        ConditionFacts(attest_client=True),
    ),
    (
        "attest_client",
        {**ALLOW, "attest_client": "only"},
        ConditionFacts(attest_client=True),
        ConditionFacts(attest_client=False),
    ),
    (
        "attest_client",
        {**ALLOW, "attest_client": "only"},
        ConditionFacts(attest_client=True),
        ConditionFacts(attest_client=None),
    ),
    (
        "gates_met",
        {**ALLOW, "gates_met": "G5,G6,G7"},
        ConditionFacts(gates={"G5": True, "G6": True, "G7": True}),
        ConditionFacts(gates={"G5": True, "G6": False, "G7": True}),
    ),
    (
        "gates_met",
        {**ALLOW, "gates_met": "G3"},
        ConditionFacts(gates={"G3": True}),
        ConditionFacts(gates=None),
    ),
    (
        "scope_only",
        {"client_admin": "allow", "scope_only": "required"},
        ConditionFacts(client_actor=True, scope_covered=True),
        ConditionFacts(client_actor=True, scope_covered=False),
    ),
    (
        "scope_only",
        {"client_admin": "allow", "scope_only": "required"},
        ConditionFacts(client_actor=True, scope_covered=True),
        ConditionFacts(client_actor=True, scope_covered=None),
    ),
]
IDS = [f"{c[0]}-{i}" for i, c in enumerate(CASES)]


def test_every_condition_has_an_allow_and_a_deny_case() -> None:
    assert {c[0] for c in CASES} == CONDITION_KEYS


@pytest.mark.parametrize(("condition", "entries", "allow", "deny"), CASES, ids=IDS)
def test_condition_allows_when_its_facts_hold(
    condition: str, entries: dict[str, str], allow: ConditionFacts, deny: ConditionFacts
) -> None:
    rule = _rule("probe.act", entries)
    assert conditions_hold(rule, allow, person=True), condition


@pytest.mark.parametrize(("condition", "entries", "allow", "deny"), CASES, ids=IDS)
def test_condition_denies_when_its_facts_fail_or_are_unknown(
    condition: str, entries: dict[str, str], allow: ConditionFacts, deny: ConditionFacts
) -> None:
    rule = _rule("probe.act", entries)
    assert not conditions_hold(rule, deny, person=True), condition


def test_a_rule_without_conditions_holds() -> None:
    assert conditions_hold(_rule("probe.act", ALLOW), ConditionFacts(), person=True)


def test_agents_and_runs_are_bound_by_resource_conditions_not_actor_ones() -> None:
    actor = _rule("probe.act", {**ALLOW, "level_in": "partner", "not_offshore": "required"})
    assert conditions_hold(actor, ConditionFacts(), person=False)
    resource = _rule("probe.act", {**ALLOW, "gates_met": "G3"})
    assert not conditions_hold(resource, ConditionFacts(gates={"G3": False}), person=False)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("level_in", "intern"),
        ("function_in", "approver"),
        ("gates_met", "G10"),
        ("attest_client", "maybe"),
        ("not_offshore", "yes"),
        ("scope_only", "true"),
    ],
)
def test_an_unknown_condition_value_is_an_import_error(key: str, value: str) -> None:
    with pytest.raises(ValueError, match="unknown value"):
        _rule("probe.act", {**ALLOW, key: value})


def test_firm_setting_names_are_kept_per_role() -> None:
    rule = _rule("probe.act", {"senior": "firm_setting(seniors_can_accept)"})
    assert rule.firm_settings == (("senior", "seniors_can_accept"),)


# --- in_scope: a practice leader's service lines, never anything else -------------------------


def _leader() -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        "practice_leader",
        datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("lines", "engagement_line", "expected"),
    [({"tax"}, "tax", True), ({"audit"}, "tax", False), (set[str](), "tax", False)],
)
async def test_in_scope_is_the_service_line_match(
    monkeypatch: pytest.MonkeyPatch, lines: set[str], engagement_line: str, expected: bool
) -> None:
    async def facts(*_: object) -> MemberFacts:
        return MemberFacts(
            level="partner", offshore=False, service_lines=frozenset(lines), client=False
        )

    async def line(*_: object) -> str:
        return engagement_line

    monkeypatch.setattr(authz, "member_facts", facts)
    monkeypatch.setattr(authz.LOOKUPS, "service_line", line)
    ctx = _leader()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    _, scoped = await authz._in_scope(ctx, "practice_leader", resource, None)  # pyright: ignore[reportPrivateUsage]  # the rule, tested directly
    assert scoped is expected


async def test_in_scope_never_reaches_beyond_the_scoped_roles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def line(*_: object) -> str:
        return "tax"

    monkeypatch.setattr(authz.LOOKUPS, "service_line", line)
    ctx = _leader()
    resource = Resource.engagement(ctx.tenant_id, uuid.uuid4(), archived=False)
    _, scoped = await authz._in_scope(ctx, "manager", resource, None)  # pyright: ignore[reportPrivateUsage]  # the rule, tested directly
    assert scoped is False
