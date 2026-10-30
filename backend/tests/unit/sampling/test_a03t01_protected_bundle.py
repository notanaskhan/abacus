"""A-03-T01 (DEC-1550; A-03 §4.3, §4.7; SPEC-580 AC-1 to AC-3): the S20 protected bundle for A-03.

Acceptance: "generated tests deny the agent, support and portal principals every A-03 write, and
import-linter rejects a compute import of any module" (the contract is switched on by A-03-T21).
The generated suites carry the per-role cases; this file pins the rows they are generated from,
so a widened row fails here as well as in the generated diff."""

from __future__ import annotations

import pytest
import yaml

from abacus.kernel import _flags
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import feature_flags
from abacus_tools.quality.banned_patterns import MODULE_DEPENDENCIES
from abacus_tools.quality.fresh_mfa import REGISTER

WRITES = (
    "population.create",
    "sample_set.create",
    "sample_set.approve",
    "sample_set.export",
    "sample_set.generate_requests",
    "grouping_set.import",
    "grouping_set.publish",
    "mapping_set.edit",
    "mapping_set.confirm",
    "account_mapping.edit",
)
SYSTEM_START = "mapping_set.run"
READS = ("population.read", "sample_set.read", "grouping_set.read", "mapping_set.read")
PORTAL = ("client_admin", "client_contributor", "third_party")
SUPPORT = ("platform_support", "platform_support_content")
TEAM = ("engagement_partner", "manager", "senior", "staff", "reviewer", "eqr_reviewer")


@pytest.mark.parametrize("action", (*WRITES, SYSTEM_START))
def test_ac1_every_a03_write_denies_the_agent_support_and_the_portal(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions.get("agent") == "deny", action
    for role in (*PORTAL, *SUPPORT):
        assert decisions.get(role, "deny") == "deny", (action, role)


@pytest.mark.parametrize("action", WRITES)
def test_ac1_the_system_holds_no_a03_write(action: str) -> None:
    assert RULES[action].decisions.get("system", "deny") == "deny", action


def test_ac1_the_system_only_starts_a_mapping_run() -> None:
    # The trial_balance.version_created subscriber dispatches the run as system (A-03 §4.4).
    decisions = RULES[SYSTEM_START].decisions
    assert decisions.get("system") == "allow"
    assert {r for r, d in decisions.items() if d == "allow"} == {
        "engagement_partner",
        "manager",
        "senior",
        "system",
    }


@pytest.mark.parametrize("action", READS)
def test_ac1_reads_are_the_teams_and_the_agent_only_at_task_scope(action: str) -> None:
    decisions = RULES[action].decisions
    for role in TEAM:
        assert decisions.get(role) == "allow", (action, role)
    assert decisions.get("agent") == "task_scope"
    for role in (*PORTAL, *SUPPORT, "system"):
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_ac2_approval_is_never_the_preparers_and_publishing_needs_a_fresh_factor() -> None:
    approve = RULES["sample_set.approve"]
    assert approve.not_preparer_of_target
    assert {r for r, d in approve.decisions.items() if d == "allow"} == {
        "engagement_partner",
        "manager",
    }
    assert RULES["grouping_set.publish"].mfa_recent
    register = yaml.safe_load(REGISTER.read_text(encoding="utf-8"))
    assert "grouping_set.publish" in {str(item["action"]) for item in register["actions"]}


def test_ac3_the_two_flags_exist_and_default_off() -> None:
    assert _flags.SAMPLING_SAMPLE_SETS.name == "sampling.sample_sets"
    assert _flags.LEDGER_TB_MAPPING.name == "ledger.tb_mapping"
    for flag in (_flags.SAMPLING_SAMPLE_SETS, _flags.LEDGER_TB_MAPPING):
        assert flag.default == "false"
    names = {entry.name for entry in feature_flags.parse(feature_flags.source())}
    assert {"sampling.sample_sets", "ledger.tb_mapping"} <= names


def test_ac3_sampling_reaches_methodology_review_and_requests_and_ledger_stays_bare() -> None:
    assert {"methodology", "review", "requests"} <= MODULE_DEPENDENCIES["sampling"]
    assert MODULE_DEPENDENCIES["ledger"] == frozenset()
    for module in ("methodology", "review", "requests"):
        assert "sampling" not in MODULE_DEPENDENCIES[module], module

