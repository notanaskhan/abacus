"""Q-02 AC-42 (first half; Q-02-T30): every action in `docs/architecture/fresh-mfa-actions.yaml`
exists in the permission matrix and carries `mfa_recent: required`. Removing the condition from a
listed action fails here. Q-02-T37 adds the lint (`abacus_tools.quality.fresh_mfa`, tested in
`test_fresh_mfa_lint.py`) and the generated overlay (`test_fresh_mfa_generated.py`)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.identity.authz.matrix import RULES

REGISTER = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "fresh-mfa-actions.yaml"
GROUPS = frozenset(
    {"wall", "ai_policy", "export", "legal_hold", "independence", "data_boundary", "reveal"}
    | {"portal_access"}  # P-07-T25 (DEC-303), P-08-T21: a client's portal unlock and MFA reset
    | {"team"}  # P-07-T30 (DEC-327): the engagement partner's team approval
    | {"access_control"}  # P-08-T21 security review: security-role changes
    | {"incident"}  # G-02-T02 (Q-02 AC-42): incident decisions
    | {"sign_off"}  # P-04-T22 (DEC-501): bulk sign-off
)


def _listed() -> list[dict[str, str]]:
    data = cast(dict[str, object], yaml.safe_load(REGISTER.read_text(encoding="utf-8")))
    return cast(list[dict[str, str]], data["actions"])


LISTED = sorted(entry["action"] for entry in _listed())


def test_each_action_is_listed_once_in_a_known_group() -> None:
    assert len(LISTED) == len(set(LISTED))
    assert {entry["group"] for entry in _listed()} <= GROUPS


@pytest.mark.parametrize("action", LISTED)
def test_ac42_a_listed_action_needs_a_fresh_second_factor(action: str) -> None:
    assert action in RULES, f"{action} is not in the permission matrix"
    assert RULES[action].mfa_recent, f"{action} lacks mfa_recent: required"


def test_ac42_the_legal_hold_and_export_writes_are_listed() -> None:
    assert {"legal_hold.place", "legal_hold.lift", "firm_export.approve"} <= set(LISTED)


def test_g02_ac45_the_governance_writes_need_a_fresh_second_factor() -> None:
    """SPEC-349 AC-45 (G-02-T02): the firm-governance writes are on the list."""
    governance = {"incident.decide", "ai_policy.publish", "ai_policy.approve"}
    governance |= {"audit_event.export", "firm_export.schedule", "security.manage"}
    governance |= {"session.end", "staff.unlock"}
    assert governance <= set(LISTED)
    assert "trial_balance.export" in LISTED  # A-02 security review (DEC-316, amended)


def test_p08t21_the_portal_unlock_and_mfa_reset_are_listed() -> None:
    assert {"contact.unlock", "contact.mfa_reset"} <= set(LISTED)
