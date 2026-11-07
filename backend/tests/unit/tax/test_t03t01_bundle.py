"""T-03-T01 (DEC-2200; T-03 §4.3, §4.7, §4.8): the T-03 protected bundle.

Acceptance: "generated tests deny the agent and portal principals every T-03 write and deny
payment approval to a user without the reviewer function." The generated suites carry the
per-role cases; this file pins the rows they are generated from."""

from __future__ import annotations

import pytest

from abacus.kernel import _flags
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.notifications import (
    catalogue,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- registers the kinds
)
from abacus.modules.notifications.kinds import kind_of
from abacus_tools.codegen import feature_flags

WRITES = (
    "questionnaire.edit",
    "questionnaire_template.draft",
    "questionnaire_template.assign_owner",
    "filing_extension.prepare",
    "filing_extension.approve_payment",
    "filing_extension.mark_filed",
    "filing_extension.flag_likely",
    "filing_extension.confirmation_send",
    "estimate_schedule.update",
    "estimate_schedule.confirmation_send",
    "tax_schedule.export",
)
TAX_READS = ("filing_extension.read", "estimate_schedule.read")
PORTAL = ("client_admin", "client_contributor", "third_party")
SUPPORT = ("platform_support", "platform_support_content")
KINDS = ("extension_ack_rejected", "extension_payment_approval_requested", "estimate_due_soon")


@pytest.mark.parametrize("action", WRITES)
def test_ac1_every_t03_write_denies_the_agent_system_support_and_the_portal(action: str) -> None:
    rule = RULES[action]
    assert rule.decisions.get("agent") == "deny", action
    assert rule.decisions.get("system", "deny") == "deny", action
    for role in (*PORTAL, *SUPPORT):
        assert rule.decisions.get(role, "deny") == "deny", (action, role)


@pytest.mark.parametrize(
    "action",
    [
        a
        for a in WRITES
        if a.split(".")[0]
        in {"filing_extension", "estimate_schedule", "tax_schedule", "questionnaire"}
    ],
)
def test_ac1_client_data_writes_fail_closed_offshore(action: str) -> None:
    assert RULES[action].not_offshore, action  # DEC-2200, as DEC-2050


def test_ac1_payment_approval_needs_the_reviewer_function_and_never_client_service() -> None:
    rule = RULES["filing_extension.approve_payment"]
    assert rule.function_in == frozenset({"detail_reviewer", "manager_reviewer", "signer"})
    assert rule.decisions.get("client_service", "deny") == "deny"
    assert "preparer" not in rule.function_in


@pytest.mark.parametrize("action", TAX_READS)
def test_ac1_reads_are_the_firms_and_the_agent_only_at_task_scope(action: str) -> None:
    decisions = RULES[action].decisions
    for role in (
        "firm_admin",
        "engagement_partner",
        "manager",
        "senior",
        "staff",
        "client_service",
    ):
        assert decisions.get(role) == "allow", (action, role)
    assert decisions.get("agent") == "task_scope"
    for role in (*PORTAL, *SUPPORT, "system"):
        assert decisions.get(role, "deny") == "deny", (action, role)


def test_ac1_export_needs_a_fresh_second_factor_and_a_manager() -> None:
    rule = RULES["tax_schedule.export"]
    assert rule.mfa_recent
    assert rule.decisions.get("senior", "deny") == "deny"
    assert rule.decisions.get("staff", "deny") == "deny"


def test_ac1_assure_estimate_actions_stay_assurances() -> None:
    # assurance owns estimate.* (AUD-27); tax uses estimate_schedule.* (DEC-2200)
    assert "estimate.update" not in RULES
    assert "extension.read" not in RULES


def test_ac1_the_two_flags_are_retired() -> None:
    # T-03-T18 (DEC-2605): the `tax_returns` entitlement gates both route families instead.
    assert not hasattr(_flags, "QUESTIONNAIRES_EDITOR")
    assert not hasattr(_flags, "TAX_EXTENSIONS_ESTIMATES")
    names = {entry.name for entry in feature_flags.parse(feature_flags.source())}
    assert not {"questionnaires.editor", "tax.extensions_estimates"} & names


@pytest.mark.parametrize("kind", KINDS)
def test_ac1_the_three_c16_kinds_are_registered(kind: str) -> None:
    assert kind_of(kind) is not None
