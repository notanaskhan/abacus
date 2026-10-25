"""Q-02 AC-42 (first half; Q-02-T30): every action in `docs/architecture/fresh-mfa-actions.yaml`
exists in the permission matrix and carries `mfa_recent: required`. Removing the condition from a
listed action fails here. Q-02-T37 adds the generated overlay and the staff-route check."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
import yaml

from abacus.modules.identity.authz.matrix import RULES

REGISTER = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "fresh-mfa-actions.yaml"
GROUPS = frozenset(
    {"wall", "ai_policy", "export", "legal_hold", "independence", "data_boundary", "reveal"}
    | {"portal_access"}  # P-07-T25 (DEC-303): clearing a client's portal sign-in lock
    | {"team"}  # P-07-T30 (DEC-327): the engagement partner's team approval
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
