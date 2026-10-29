"""Generate the security suite's table-driven tests (Q-02-T13; ADR-080).

- `tests/security/test_tenant_isolation.py`: one case per tenant-scoped table in the module
  registries (`schema_check.TABLE_OWNERS`, less the platform's non-tenant and global tables).
- `tests/security/test_permission_matrix_generated.py`: one case per (action, human role) with
  the outcome the matrix states, conditions included: an allow is an allow only when no
  condition needs facts the harness doesn't give (level, function, offshore, attest client,
  gates; `scope_only` for a client role), and every conditional decision (`in_scope`,
  `firm_setting(...)`, `assigned_only`, `client_visible_only`, `task_scope`) denies without its
  facts. Reviewing the generated file's diff is reviewing the matrix change.
- `tests/security/test_resolution_actions_generated.py` (P-04-T15; I-AGENT-NEVER, ADR-005):
  every resolution action (each sign-off, decision, proposal, suggestion, checkpoint, review
  decision and evidence decision that is not a read or an agent's own proposing, and the issue
  resolutions) denied to an agent, a system run and a support session; and the target
  conditions `not_preparer_of_target`, `reserved_role` and `owner_of_target` (K-02-T01), allow
  and deny, for every role their row allows. K-02-T01 adds the firm-standard writes: a person's
  acts (INV-1), never an agent's, a system run's or a support session's.
- `tests/security/test_fresh_mfa_generated.py` (Q-02-T37; Q-02 AC-42): for each action in
  `docs/architecture/fresh-mfa-actions.yaml`, the matrix carries `mfa_recent: required`, a role
  the row allows is refused without a second factor verified in the last 15 minutes (never, or
  just over) and allowed with one, and the routes that declare it (each refuses to answer unless
  its declared action was authorised, `AbacusRoute`) still declare it. Removing the condition,
  the listing or a route's declaration shows in this file's diff and fails.
- `tests/security/test_route_introspection.py` (Q-02-T15): one case per (method, path) that
  `create_app()` serves through `AbacusRouter`, with the action it declares, and the routes that
  answer without a token. Each case checks one matrix action (or route marker), a response model
  and the authentication that action needs; the unauthenticated ones must be the public-route
  list (P-45, ADR-152). A route without an action is listed with an empty action and fails.

`--check` fails when any file differs from what its sources give (`make check-generated`),
so a hand edit fails CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

from abacus_tools.quality.schema_check import GLOBAL_TABLES, NON_TENANT_TABLES, TABLE_OWNERS

if TYPE_CHECKING:
    from fastapi import FastAPI

    from abacus.modules.identity.api import Rule

ROOT = Path(__file__).resolve().parents[3]
ISOLATION = ROOT / "tests" / "security" / "test_tenant_isolation.py"
MATRIX = ROOT / "tests" / "security" / "test_permission_matrix_generated.py"
INTROSPECTION = ROOT / "tests" / "security" / "test_route_introspection.py"
RESOLUTION = ROOT / "tests" / "security" / "test_resolution_actions_generated.py"
FRESH_MFA = ROOT / "tests" / "security" / "test_fresh_mfa_generated.py"
FRESH_MFA_REGISTER = ROOT.parent / "docs" / "architecture" / "fresh-mfa-actions.yaml"
# P-04-T15: the entities whose every non-read action is a person's resolution, the issue
# resolutions, and the evidence decisions. An action the agent holds by task scope (it proposes:
# `proposal.create`, `suggestion.create`, `checkpoint.propose`) is the agent's, not a resolution.
RESOLUTION_ENTITIES = frozenset(
    {"sign_off", "decision", "proposal", "suggestion", "checkpoint", "review_decision"}
    | {"firm_standard"}  # K-02-T01 (INV-1): drafting, importing and publishing are a person's
)
RESOLUTION_ACTIONS = frozenset(
    {"issue.resolve", "issue.verify", "issue.reopen", "evidence.accept", "evidence.reject"}
)
PRINCIPALS = ("agent", "system", "support")
PREPARER_VARIANTS = (("preparer", "deny"), ("not_preparer", "allow"), ("no_facts", "deny"))
RESERVED_VARIANTS = (
    ("holder", "allow"),
    ("other_person", "deny"),
    ("other_role", "deny"),
    ("no_facts", "deny"),
)
# K-02-T01: the owner of a firm standard, a current partner, or not; or no facts at all.
OWNER_VARIANTS = (("owner", "allow"), ("not_owner", "deny"), ("no_facts", "deny"))
# The derived partner cell (DEC-132), as `identity.authz` spells it: the only role an
# `owner_of_target` row allows, so the condition's cases are generated for it too (K-02-T01).
FIRM_PARTNER = "firm_partner"
FIRM_ROLES = ("firm_admin", "practice_leader", "quality_partner", "security_admin")
ENGAGEMENT_ROLES = (
    *("engagement_partner", "manager", "senior", "staff", "reviewer"),
    *("eqr_reviewer", "specialist", "client_service"),
)
CLIENT_ROLES = ("client_admin", "client_contributor", "third_party")  # R-01-T13: third_party
HUMAN_ROLES = (*FIRM_ROLES, *ENGAGEMENT_ROLES, *CLIENT_ROLES)
_HEADER = (
    "# GENERATED by abacus_tools.codegen.security_tests (Q-02-T13). Do not edit: run\n"
    "# `make regenerate`; `make check-generated` fails on any hand edit.\n"
)
# A route that isn't an HTTP route (a mount, a websocket) has no methods: it is listed as this.
ANY_METHOD = "ANY"
LINE_LENGTH = 99  # ruff's, in pyproject.toml
Guarded = tuple[str, str, str]  # method, path, declared action ("" when it declares none)
Unguarded = tuple[str, str]  # method, path


def _q(text: str) -> str:
    return json.dumps(text)


def tenant_tables() -> list[str]:
    return sorted(set(TABLE_OWNERS) - NON_TENANT_TABLES - GLOBAL_TABLES)


def expected(rule: Rule, role: str) -> str:
    """What `authorise` must answer for `role`, everything but the matrix satisfied."""
    if rule.decisions.get(role) != "allow":
        return "deny"
    if rule.level_in or rule.function_in or rule.not_offshore:
        return "deny"
    if rule.attest_client is not None or rule.gates_met:
        return "deny"
    if rule.scope_only and role in CLIENT_ROLES:
        return "deny"
    if rule.not_preparer_of_target or rule.reserved_role or rule.owner_of_target:
        return "deny"  # P-04-T15, K-02-T01: no target facts in the harness (fail closed)
    return "allow"


def resolution_actions(rules: dict[str, Rule]) -> list[str]:
    """P-04-T15: every action a person resolves and nothing else may (I-AGENT-NEVER)."""
    return sorted(
        action
        for action, rule in rules.items()
        if action in RESOLUTION_ACTIONS
        or (
            action.split(".", 1)[0] in RESOLUTION_ENTITIES
            and not rule.reads
            and rule.decisions.get("agent") != "task_scope"
        )
    )


def condition_cases(rules: dict[str, Rule]) -> list[tuple[str, str, str, str]]:
    """Allow and deny for each target condition, for every role its row would otherwise allow."""
    cases: list[tuple[str, str, str, str]] = []
    for action, rule in sorted(rules.items()):
        if not (rule.not_preparer_of_target or rule.reserved_role or rule.owner_of_target):
            continue
        others = replace(
            rule, not_preparer_of_target=False, reserved_role=False, owner_of_target=False
        )
        if rule.owner_of_target:
            variants = OWNER_VARIANTS
        elif rule.not_preparer_of_target:
            variants = PREPARER_VARIANTS
        else:
            variants = RESERVED_VARIANTS
        for role in (*HUMAN_ROLES, FIRM_PARTNER):
            if expected(others, role) != "allow":
                continue
            cases += [(action, role, variant, want) for variant, want in variants]
    return cases


def render_isolation() -> str:
    rows = "".join(f"    {_q(name)},\n" for name in tenant_tables())
    return (
        _HEADER
        + '"""ADR-014 table by table: row-level security on, forced and keyed to the tenant, and\n'
        + "nothing of firm B's read under firm A, for every tenant-scoped table the module\n"
        + 'registries name."""\n\n'
        + "from __future__ import annotations\n\n"
        + "import pytest\n\n"
        + "from .isolation import problems\n"
        + "from .support import Seeder, TwoFirms, two_firms\n\n"
        + f"TABLES: tuple[str, ...] = (\n{rows})\n\n\n"
        + '@pytest.mark.parametrize("name", TABLES)\n'
        + "async def test_adr014_the_table_isolates_tenants(seed: Seeder, name: str) -> None:\n"
        + "    firms: TwoFirms = await two_firms(seed)\n"
        + "    assert await problems(seed, name, firms.a_ctx, firms.b) == []\n"
    )


def render_matrix() -> str:
    from abacus.modules.identity.api import RULES  # tooling may import product

    cases = "".join(
        f"    ({_q(action)}, {_q(role)}, {_q(expected(rule, role))}),\n"
        for action, rule in sorted(RULES.items())
        for role in HUMAN_ROLES
    )
    return (
        _HEADER
        + '"""Every (action, human role) of the permission matrix, allow and deny, with its\n'
        + 'conditions (ADR-080). The outcome is `authorise`\'s, through `matrix_harness`."""\n\n'
        + "from __future__ import annotations\n\n"
        + "import pytest\n\n"
        + "from .matrix_harness import outcome\n\n"
        + f"CASES: tuple[tuple[str, str, str], ...] = (\n{cases})\n\n\n"
        + '@pytest.mark.parametrize(("action", "role", "want"), CASES)\n'
        + "async def test_adr080_the_matrix_decides(\n"
        + "    monkeypatch: pytest.MonkeyPatch, action: str, role: str, want: str\n"
        + ") -> None:\n"
        + "    assert await outcome(monkeypatch, action, role) == want\n"
    )


def render_resolution() -> str:
    from abacus.modules.identity.api import RULES  # tooling may import product

    denied = "".join(
        _row(action, principal) for action in resolution_actions(RULES) for principal in PRINCIPALS
    )
    conditions = "".join(_row(*case) for case in condition_cases(RULES))
    doc = (
        '"""I-AGENT-NEVER for every resolution action (ADR-005; P-04-T15): an agent, a system\n'
        "run and a support session are denied each one, whatever facts a person would need are\n"
        "given. And the target conditions, allow and deny: a preparer never signs L2 or L3 on\n"
        "their own target (`not_preparer_of_target`), and only the person holding a card's\n"
        "reserved role decides it (`reserved_role`). Only a firm standard's owner, a partner\n"
        "now, drafts or publishes it (`owner_of_target`, K-02-T01). Reviewing this diff is\n"
        'reviewing the rule."""\n\n'
    )
    harness = "Principal, Variant, condition_outcome, principal_outcome"
    signature = "action: str, role: str, variant: Variant, want: str"
    return (
        _HEADER.replace("(Q-02-T13)", "(P-04-T15)")
        + doc
        + "from __future__ import annotations\n\n"
        + "import pytest\n\n"
        + f"from .matrix_harness import {harness}\n\n"
        + f"NEVER: tuple[tuple[str, str], ...] = (\n{denied})\n"
        + f"CONDITIONS: tuple[tuple[str, str, str, str], ...] = (\n{conditions})\n\n\n"
        + '@pytest.mark.parametrize(("action", "principal"), NEVER)\n'
        + "async def test_i_agent_never_the_principal_is_denied(\n"
        + "    monkeypatch: pytest.MonkeyPatch, action: str, principal: Principal\n"
        + ") -> None:\n"
        + '    assert await principal_outcome(monkeypatch, action, principal) == "deny"\n\n\n'
        + '@pytest.mark.parametrize(("action", "role", "variant", "want"), CONDITIONS)\n'
        + "async def test_p04t15_the_target_condition_decides(\n"
        + f"    monkeypatch: pytest.MonkeyPatch, {signature}\n"
        + ") -> None:\n"
        + "    assert await condition_outcome(monkeypatch, action, role, variant) == want\n"
    )


def served(app: FastAPI) -> tuple[list[Guarded], list[Unguarded]]:
    """What `app` serves: the routes `AbacusRouter` built (authenticated, with their declared
    action) and every other route, which answers without a token. Sorted, one row per method."""
    from fastapi.routing import iter_route_contexts

    from abacus.modules.identity.api import AbacusRoute, declared_action

    guarded: list[Guarded] = []
    unguarded: list[Unguarded] = []
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        path = context.path or str(getattr(route, "path", "?"))
        methods = sorted(cast("set[str] | None", getattr(route, "methods", None)) or {ANY_METHOD})
        if isinstance(route, AbacusRoute):
            action = declared_action(route) or ""
            guarded += [(method, path, action) for method in methods]
        else:
            unguarded += [(method, path) for method in methods]
    return sorted(guarded), sorted(unguarded)


def _row(*values: str) -> str:
    """One tuple of a table as `ruff format` lays it out: on one line when it fits, else one
    value per line."""
    line = f"    ({', '.join(_q(v) for v in values)}),\n"
    if len(line) - 1 <= LINE_LENGTH:
        return line
    return "    (\n" + "".join(f"        {_q(v)},\n" for v in values) + "    ),\n"


def fresh_mfa_listed() -> list[tuple[str, str]]:
    """(action, group) for each action the fresh-MFA register lists, in its order."""
    import yaml

    data = cast(dict[str, object], yaml.safe_load(FRESH_MFA_REGISTER.read_text(encoding="utf-8")))
    entries = cast(list[dict[str, str]], data["actions"])
    return [(entry["action"], entry["group"]) for entry in entries]


def fresh_mfa_role(rule: Rule) -> str:
    """A role the row allows once its conditions are cleared (the MFA case isolates the
    attribute); the derived `firm_partner` cell when only it allows; "" when none does."""
    for role in HUMAN_ROLES:
        if rule.decisions.get(role) == "allow" and not (rule.scope_only and role in CLIENT_ROLES):
            return role
    return FIRM_PARTNER if rule.decisions.get(FIRM_PARTNER) == "allow" else ""


def render_fresh_mfa() -> str:
    from abacus.api import create_app  # tooling may import product
    from abacus.modules.identity.api import RULES

    listed = fresh_mfa_listed()
    actions = {action for action, _ in listed}
    cases = "".join(
        _row(action, group, fresh_mfa_role(RULES[action]) if action in RULES else "")
        for action, group in listed
    )
    guarded, _ = served(create_app())
    routes = "".join(_row(*row) for row in guarded if row[2] in actions)
    return (
        _HEADER.replace("(Q-02-T13)", "(Q-02-T37)")
        + '"""The fresh-MFA overlay (Q-02 AC-42; Q-02-T37): every action in\n'
        + "`docs/architecture/fresh-mfa-actions.yaml` carries `mfa_recent: required`; a role\n"
        + "its row allows is refused without a second factor verified in the last 15 minutes\n"
        + "and allowed with one; and every route declaring a listed action still declares it\n"
        + "(a route answers only after its declared action was authorised, `AbacusRoute`). An\n"
        + "action no route declares yet is enforced wherever its service calls `authorise`.\n"
        + '"""\n\n'
        + "from __future__ import annotations\n\n"
        + "import pytest\n\n"
        + "from abacus.modules.identity.api import RULES\n"
        + "from abacus_tools.codegen.security_tests import served\n\n"
        + "from .matrix_harness import Freshness, mfa_outcome\n"
        + "from .route_checks import app\n\n"
        + f"CASES: tuple[tuple[str, str, str], ...] = (\n{cases})\n"
        + f"ROUTES: tuple[tuple[str, str, str], ...] = (\n{routes})\n"
        + "LISTED = frozenset(action for action, _, _ in CASES)\n\n\n"
        + '@pytest.mark.parametrize(("action", "group", "role"), CASES)\n'
        + "def test_ac42_the_listed_action_needs_a_fresh_second_factor(\n"
        + "    action: str, group: str, role: str\n"
        + ") -> None:\n"
        + '    assert action in RULES, f"{action} ({group}) is not in the permission matrix"\n'
        + '    assert RULES[action].mfa_recent, f"{action} lacks mfa_recent: required"\n'
        + '    assert role, f"{action}: no human role may, so nothing shows the MFA rule"\n'
        + "\n\n"
        + '@pytest.mark.parametrize(("action", "group", "role"), CASES)\n'
        + "@pytest.mark.parametrize(\n"
        + '    ("freshness", "want"), [("fresh", "allow"), ("stale", "deny"), ("none", "deny")]\n'
        + ")\n"
        + "async def test_ac42_authorise_refuses_without_a_fresh_second_factor(\n"
        + "    monkeypatch: pytest.MonkeyPatch,\n"
        + "    action: str,\n"
        + "    group: str,\n"
        + "    role: str,\n"
        + "    freshness: Freshness,\n"
        + "    want: str,\n"
        + ") -> None:\n"
        + "    assert await mfa_outcome(monkeypatch, action, role, freshness) == want\n\n\n"
        + "def test_ac42_the_routes_declaring_a_listed_action_are_unchanged() -> None:\n"
        + "    guarded, _ = served(app())\n"
        + "    assert [row for row in guarded if row[2] in LISTED] == list(ROUTES)\n"
    )


def render_introspection() -> str:
    from abacus.api import create_app  # tooling may import product

    guarded, unguarded = served(create_app())
    rows = "".join(_row(*row) for row in guarded)
    public = "".join(_row(*row) for row in unguarded)
    return (
        _HEADER.replace("(Q-02-T13)", "(Q-02-T15)")
        + '"""Every route `create_app()` serves (ADR-012, ADR-027, ADR-152; Q-02-T15): each\n'
        + "one `AbacusRouter` built declares exactly one action from the permission matrix (or\n"
        + "a route marker), a response model and the authentication that action needs, and the\n"
        + "only routes answering without a token are the public-route list (P-45). The table is\n"
        + "read from the app, so reviewing this file's diff is reviewing the API surface.\n"
        + '"""\n\n'
        + "from __future__ import annotations\n\n"
        + "import pytest\n\n"
        + "from abacus_tools.codegen.security_tests import served\n\n"
        + "from .route_checks import app, openapi_problems, public_problems, route_problems\n\n"
        + f"ROUTES: tuple[tuple[str, str, str], ...] = (\n{rows})\n"
        + f"UNAUTHENTICATED: tuple[tuple[str, str], ...] = (\n{public})\n\n\n"
        + "@pytest.fixture(autouse=True)\n"
        + "def engines() -> None:\n"
        + '    """Routes are read from the app, not a database: this file needs no container."""\n'
        + "\n\n"
        + "def test_q02_the_app_serves_exactly_the_generated_routes() -> None:\n"
        + "    assert served(app()) == (list(ROUTES), list(UNAUTHENTICATED))\n\n\n"
        + '@pytest.mark.parametrize(("method", "path", "action"), ROUTES)\n'
        + "def test_adr027_the_route_declares_one_action_a_response_model_and_authentication(\n"
        + "    method: str, path: str, action: str\n"
        + ") -> None:\n"
        + "    assert route_problems(app(), method, path, action) == []\n\n\n"
        + "def test_p45_only_the_public_route_list_answers_without_a_token() -> None:\n"
        + "    assert public_problems(app(), UNAUTHENTICATED) == []\n\n\n"
        + "def test_adr027_every_documented_operation_is_a_generated_route() -> None:\n"
        + "    assert openapi_problems(app(), ROUTES) == []\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a file is out of date")
    args = parser.parse_args(argv)
    targets = (
        (ISOLATION, render_isolation()),
        (MATRIX, render_matrix()),
        (INTROSPECTION, render_introspection()),
        (RESOLUTION, render_resolution()),
        (FRESH_MFA, render_fresh_mfa()),
    )
    if args.check:
        stale = [p for p, body in targets if not p.exists() or p.read_text() != body]
        for path in stale:
            print(f"{path.name} is out of date: run python -m abacus_tools.codegen.security_tests")
        return 1 if stale else 0
    for path, body in targets:
        path.write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
