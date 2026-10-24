"""SPEC-333 AC-30, AC-31 (A-02-T02; TASK-1185): the protected bundle's matrix rows, registry
objects and flag. Expectations come from A-02 §4.4, §3.4 and §0, not from the YAML."""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from abacus.kernel._flags import LEDGER_TB_WORKPAPER
from abacus.kernel._statuses import TrialBalanceLabelStatus, TrialBalanceLayerStatus
from abacus.modules.identity.authz.matrix import RULES
from abacus_tools.codegen import feature_flags

# A-02 §4.4: action -> the roles allowed. The agent principal holds none (INV-1).
NEW_ACTIONS: dict[str, set[str]] = {
    "trial_balance.export": {"engagement_partner", "manager", "senior", "staff"},
    "ledger.pull": {"engagement_partner", "manager", "senior"},
    "connection.read": {"client_admin", "engagement_partner", "manager", "senior"},
    "connection.retry": {"client_admin", "engagement_partner", "manager"},
    "connection.reconnect_request": {"engagement_partner", "manager", "senior"},
}
FIRM_SIDE = ("trial_balance.export", "ledger.pull", "connection.read")


@pytest.mark.parametrize("action", sorted(NEW_ACTIONS))
def test_ac30_each_new_action_allows_exactly_its_roles_and_never_the_agent(action: str) -> None:
    rule = RULES[action]
    assert {r for r, d in rule.decisions.items() if d == "allow"} == NEW_ACTIONS[action]
    assert rule.decisions.get("agent") == "deny"
    assert rule.decisions.get("system") == "deny"
    assert not rule.mfa_recent  # Open in Excel and pulls need no fresh MFA (DEC-316)


@pytest.mark.parametrize("action", [*FIRM_SIDE, "connection.reconnect_request"])
def test_ac30_firm_side_actions_need_an_independence_confirmation(action: str) -> None:
    assert RULES[action].independence is True


def test_ac30_a_client_owner_reads_only_connections_their_grant_covers() -> None:
    assert RULES["connection.read"].scope_only is True
    assert RULES["connection.create"].mfa_recent is True  # unchanged (SPEC-020 AC-3)


def test_ac31_the_registry_emits_the_tb_labels_and_layers() -> None:
    assert [c.value for c in TrialBalanceLabelStatus] == [
        "standard",
        "interim",
        "prior",
        "budget",
        "preliminary",
    ]
    assert [c.value for c in TrialBalanceLayerStatus] == ["unadjusted", "aje", "rje", "final"]


def test_ac31_the_tb_workpaper_flag_is_boolean_default_off_and_expires_outside_busy_season() -> (
    None
):
    assert LEDGER_TB_WORKPAPER.kind == "boolean"
    assert LEDGER_TB_WORKPAPER.default == "false"
    flags = yaml.safe_load(feature_flags.source())["flags"]
    (entry,) = [f for f in flags if f["name"] == "ledger.tb_workpaper"]
    expires = entry["expires"]
    assert isinstance(expires, date)
    assert not date(expires.year, 9, 1) <= expires <= date(expires.year, 10, 20)
    assert expires >= date(2027, 2, 1)
