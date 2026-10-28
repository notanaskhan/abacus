"""G-02-T23 (TASK-1616; ADR-186, ADR-187; SPEC-349 AC-32, AC-38): the compiled AI-policy
defaults, the twelve-gate catalogue against the permission matrix, and the stricter-only
validator.

"A generated test proves no gate row misstates the matrix approver, and a draft that loosens any
locked cell is refused" (G-02-T23 acceptance)."""

from __future__ import annotations

import copy
from typing import cast

import pytest

from abacus.modules.agents._ai_policy_defaults import GATES, LOCKS, SECTIONS, STRICTER
from abacus.modules.agents.ai_policy_errors import AiPolicyLoosened
from abacus.modules.agents.ai_policy_validator import GATE_KEYS, check_stricter_only
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import ai_policy_defaults as codegen

DECIDES = frozenset({"allow", "firm_setting", "in_scope"})
NOT_PEOPLE = frozenset({"agent", "system", "client_admin", "client_contributor", "third_party"})


def _deciders(action: str) -> set[str]:
    return {r for r, d in RULES[action].decisions.items() if d in DECIDES} - NOT_PEOPLE


def test_the_generated_module_is_current() -> None:
    assert codegen.main(["--check"]) == 0


def test_ac32_the_catalogue_holds_twelve_gates_in_order() -> None:
    assert [g["row"] for g in GATES] == list(range(1, 13))
    assert len(GATE_KEYS) == 12


@pytest.mark.parametrize("gate", GATES, ids=[str(g["gate_key"]) for g in GATES])
def test_ac32_no_gate_misstates_the_matrix_approver(gate: dict[str, object]) -> None:
    actions = cast(list[str], gate["actions"])
    roles = set(cast(list[str], gate["approver_roles"]))
    for action in actions:
        assert action in RULES, action
        assert _deciders(action) == roles, (gate["gate_key"], action)
        assert RULES[action].decisions.get("agent") in (None, "deny")
        assert RULES[action].decisions.get("system") in (None, "deny")


def test_ac32_only_rows_1_and_5_offer_policy_acceptance() -> None:
    offered = [g["row"] for g in GATES if g.get("policy_acceptance_available")]
    assert offered == [1, 5]


def _sections() -> dict[str, object]:
    return copy.deepcopy(SECTIONS)


def test_the_defaults_themselves_pass() -> None:
    check_stricter_only(_sections())


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("policy_principal.on", True),
        ("client_data.require_7216_consent", False),
        ("client_data.client_drafts_enabled", True),
        ("auto_mode_defaults.ebp_audit", True),
        ("governance.override_tolerance_pct", 12),
        ("governance.accuracy_sample_n", 10),
        ("governance.trace_retention_years", 5),
    ],
)
def test_ac38_a_draft_that_loosens_a_cell_is_refused(path: str, value: object) -> None:
    sections = _sections()
    head, _, rest = path.partition(".")
    cast(dict[str, object], sections[head])[rest] = value
    with pytest.raises(AiPolicyLoosened) as refused:
        check_stricter_only(sections)
    assert refused.value.facts == {"field": path}


def test_ac38_gate_acceptance_stays_off_and_unknown_gates_are_refused() -> None:
    sections = _sections()
    sections["gates"] = [{"action_key": "aje_within_threshold", "policy_acceptance_on": True}]
    with pytest.raises(AiPolicyLoosened):
        check_stricter_only(sections)
    sections["gates"] = [{"action_key": "not_a_gate", "policy_acceptance_on": False}]
    with pytest.raises(AiPolicyLoosened):
        check_stricter_only(sections)


def test_stricter_changes_pass() -> None:
    sections = _sections()
    cast(dict[str, object], sections["governance"]).update(
        override_tolerance_pct=6, accuracy_sample_n=50, trace_retention_years=10
    )
    cast(dict[str, object], sections["auto_mode_defaults"]).update(tax_return=False)
    check_stricter_only(sections)


def test_every_lock_and_stricter_cell_names_a_section_cell() -> None:
    for path in (*LOCKS, *STRICTER):
        if path.startswith("gates."):
            continue
        head, _, rest = path.partition(".")
        assert rest in cast(dict[str, object], SECTIONS[head]), path
